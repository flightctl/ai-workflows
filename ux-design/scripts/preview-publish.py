#!/usr/bin/env python3
"""Preview publisher wrapper for the ux-design preview phase.

A small UX-specific project-approved PUBLISHER COMMAND wrapper.  It does
NOT perform deployment itself — it delegates to a project-owned deploy
command.  When no deploy command is configured, it returns awaiting-setup.

Contract:
  publish   Invoke the configured deploy command (or report awaiting-setup)
  verify    Check published content against its manifest

The deploy command receives four positional arguments:
  argv[1]  bundle directory (absolute path)
  argv[2]  namespace prefix (e.g. previews/org/repo/pr-42/a1b2c3d4e5f6)
  argv[3]  expected content SHA-256
  argv[4]  approved site base URL (HTTPS; HTTP only for loopback in tests)

The command MUST NOT return until the namespace and all assets are served
at the approved site URL.  The wrapper verifies served content immediately
after the command exits.

It must print a JSON receipt to stdout with at minimum:
  {"status": "published", "url": "...", "content_sha256": "..."}

For testing, --local-fixture <site-dir> provides a built-in adapter
that copies into a local directory.  Its receipt is clearly marked
"published-local" and must never be treated as live deployment.

Usage:
  preview-publish.py publish --bundle-dir <path> --pr-repo <owner/repo>
      --pr-number <N> --content-sha256 <hash> --target-repo <owner/repo>
      [--deploy-command <path> --site-url <url>] [--local-fixture <dir>]
      [--allow-test-http]
  preview-publish.py verify --site-dir <path> --namespace <prefix>
      --expected-digest <sha256>

Exit codes:
  0 -- success (or awaiting-setup)
  1 -- argument or configuration error
  2 -- verification failure (content mismatch)
  3 -- publish failure
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_VERIFY_FAIL = 2
EXIT_PUBLISH_FAIL = 3


def _fail(msg: str, code: int = EXIT_ARG_ERROR) -> NoReturn:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _validate_component(value: str, label: str) -> None:
    """Require a path-safe single component."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        _fail(f"Invalid {label}: {value!r}")


def _namespace_prefix(
    pr_repo: str, pr_number: str, content_sha: str,
) -> str:
    """Build the publication namespace from SOURCE PR identity + content digest.

    Uses *pr_repo* (where the PR lives), not target_repo, so that the
    same PR number from different source repos never collides.
    """
    owner, repo = pr_repo.split("/", 1)
    short_sha = content_sha[:12]
    return f"previews/{owner}/{repo}/pr-{pr_number}/{short_sha}"


def _load_bundler():
    """Load the bundler module for shared functions.

    Both scripts share canonical implementations — the bundler owns
    digest computation, file inventory, and HTML extension constants.
    The publisher imports them to avoid divergence.
    """
    bundler_path = Path(__file__).resolve().parent / "preview-bundle.py"
    spec = importlib.util.spec_from_file_location(
        "preview_bundle", bundler_path,
    )
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load bundler from {bundler_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bundler = _load_bundler()
_compute_content_digest = _bundler._compute_content_digest
_collect_file_inventory = _bundler._collect_file_inventory
_HTML_EXTENSIONS = _bundler._HTML_EXTENSIONS


def _validate_site_url(url: str, allow_test_http: bool = False) -> str:
    """Validate and normalize an approved site URL. Returns normalized URL."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.username or parsed.password:
        _fail("Site URL must not contain credentials")
    if parsed.query or parsed.fragment:
        _fail("Site URL must not contain query or fragment")
    if parsed.scheme == "https":
        pass  # normal production
    elif parsed.scheme == "http":
        if not allow_test_http:
            _fail("HTTP site URLs require --allow-test-http (test only)")
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            _fail("HTTP only allowed for loopback addresses in test mode")
    else:
        _fail(f"Unsupported URL scheme: {parsed.scheme!r}")
    return url.rstrip("/")


def _same_origin_opener(approved_url: str) -> tuple:
    """Build a urllib opener that rejects cross-origin redirects."""
    import urllib.request
    from urllib.parse import urlparse

    approved_origin = urlparse(approved_url)

    class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urlparse(newurl)
            if (target.scheme, target.hostname, target.port) != (
                approved_origin.scheme, approved_origin.hostname,
                approved_origin.port,
            ):
                raise urllib.error.URLError(
                    f"Cross-origin redirect to {target.scheme}://"
                    f"{target.hostname} rejected"
                )
            return super().redirect_request(
                req, fp, code, msg, headers, newurl,
            )

    opener = urllib.request.build_opener(_SameOriginRedirectHandler)
    return opener


def _verify_served_url(
    base_url: str, namespace: str, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Verify content served at *base_url/namespace/* matches *manifest*.

    Uses HTTP(S) GET for each file with same-origin redirect guard.
    Returns a dict with ``verified`` bool and ``errors`` list.
    """
    import urllib.error

    prefix = f"{base_url.rstrip('/')}/{namespace}"
    errors: list[str] = []
    opener = _same_origin_opener(base_url)

    # Verify served manifest.
    try:
        murl = f"{prefix}/preview-manifest.json"
        with opener.open(murl, timeout=10) as resp:
            served = json.loads(resp.read())
            if served.get("content_sha256") != manifest.get("content_sha256"):
                errors.append("served manifest content_sha256 differs")
    except Exception as exc:
        return {"verified": False, "errors": [f"manifest unreachable: {exc}"]}

    # Verify per-file hashes.
    from urllib.parse import quote
    for fe in manifest.get("files", []):
        furl = f"{prefix}/{quote(fe['path'], safe='/')}"
        try:
            with opener.open(furl, timeout=10) as resp:
                actual = hashlib.sha256(resp.read()).hexdigest()
                if actual != fe.get("sha256", ""):
                    errors.append(f"hash mismatch: {fe['path']}")
        except Exception:
            errors.append(f"unreachable: {fe['path']}")

    return {"verified": len(errors) == 0, "errors": errors}


def _local_fixture_publish(
    bundle_dir: Path, site_dir: Path, namespace: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """TEST FIXTURE: copy bundle into a local site directory.

    Returns a receipt clearly marked as local.  This must never be
    treated as a live Pages deployment.
    """
    dest = site_dir / namespace
    if dest.exists():
        _fail(
            f"Destination already exists: {dest}. "
            "Use a different content revision to preserve existing content.",
            EXIT_PUBLISH_FAIL,
        )

    # Snapshot existing site content.
    existing_before: set[str] = set()
    if site_dir.exists():
        existing_before = {
            str(f.relative_to(site_dir))
            for f in site_dir.rglob("*") if f.is_file()
        }

    # Path containment: bundle_dir must not be inside site_dir or vice versa.
    try:
        bundle_dir.resolve().relative_to(site_dir.resolve())
        _fail("bundle-dir is inside site-dir", EXIT_PUBLISH_FAIL)
    except ValueError:
        pass
    try:
        site_dir.resolve().relative_to(bundle_dir.resolve())
        _fail("site-dir is inside bundle-dir", EXIT_PUBLISH_FAIL)
    except ValueError:
        pass

    # Copy bundle into namespaced destination.
    dest.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(bundle_dir.rglob("*")):
        if not src_file.is_file() or src_file.is_symlink():
            continue
        rel = src_file.relative_to(bundle_dir)
        dst_file = dest / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

    # Compute published content digest using the canonical function.
    try:
        published_digest = _compute_content_digest(dest)
    except ValueError as exc:
        _fail(f"Published content integrity failed: {exc}", EXIT_PUBLISH_FAIL)

    # Verify existing content untouched.
    existing_after: set[str] = set()
    if site_dir.exists():
        existing_after = {
            str(f.relative_to(site_dir))
            for f in site_dir.rglob("*") if f.is_file()
            if not str(f.relative_to(site_dir)).startswith(namespace)
        }
    if existing_before != existing_after:
        missing = existing_before - existing_after
        _fail(
            f"Site preservation violated: {len(missing)} file(s) lost: "
            + ", ".join(sorted(missing)[:5]),
            EXIT_PUBLISH_FAIL,
        )

    file_count = sum(
        1 for f in dest.rglob("*")
        if f.is_file() and not f.is_symlink()
        and f != dest / "preview-manifest.json"
    )

    return {
        "status": "published-local",
        "content_sha256": published_digest,
        "manifest_sha256": manifest.get("content_sha256", ""),
        "digest_match": published_digest == manifest.get("content_sha256", ""),
        "namespace": namespace,
        "file_count": file_count,
        "site_dir": str(site_dir),
        "note": "LOCAL test fixture — not a live Pages deployment",
    }


def cmd_publish(args: list[str]) -> int:
    """Invoke the configured deploy command or report awaiting-setup."""
    import argparse
    p = argparse.ArgumentParser(prog="preview-publish publish")
    p.add_argument("--bundle-dir", required=True)
    p.add_argument("--pr-repo", required=True,
                   help="PR repository (owner/repo)")
    p.add_argument("--pr-number", required=True)
    p.add_argument("--content-sha256", required=True,
                   help="Expected content digest from manifest")
    p.add_argument("--target-repo", required=True,
                   help="Deployment target repository (owner/repo)")
    p.add_argument("--deploy-command", default=None,
                   help="Project-owned deploy command path")
    p.add_argument("--site-url", default=None,
                   help="Approved preview site base URL (required with --deploy-command)")
    p.add_argument("--local-fixture", default=None, metavar="SITE_DIR",
                   help="TEST ONLY: local file copy to site directory")
    p.add_argument("--allow-test-http", action="store_true",
                   help="TEST ONLY: allow http:// loopback URLs for adapter tests")
    opts = p.parse_args(args)

    bundle_dir = Path(opts.bundle_dir).resolve()
    if not bundle_dir.is_dir():
        _fail(f"Bundle directory does not exist: {bundle_dir}")

    manifest_path = bundle_dir / "preview-manifest.json"
    if not manifest_path.is_file():
        _fail(f"No preview-manifest.json in {bundle_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Validate PR identity.
    if not re.fullmatch(r"\d+", opts.pr_number):
        _fail(f"Invalid PR number: {opts.pr_number!r}")
    for label, val in [("pr-repo", opts.pr_repo), ("target-repo", opts.target_repo)]:
        if "/" not in val:
            _fail(f"Invalid {label}: {val!r} (expected owner/repo)")
        owner, repo = val.split("/", 1)
        _validate_component(owner, f"{label} owner")
        _validate_component(repo, f"{label} repo")

    # Validate content SHA-256 is well-formed and matches manifest.
    if not re.fullmatch(r"[0-9a-f]{64}", opts.content_sha256):
        _fail("content-sha256 must be 64 lowercase hex characters")
    if manifest.get("content_sha256") != opts.content_sha256:
        _fail(
            "content-sha256 does not match bundle manifest "
            f"(expected {manifest.get('content_sha256', '?')[:16]}…, "
            f"got {opts.content_sha256[:16]}…)",
        )

    # Recompute actual bundle bytes digest to catch post-packaging mutations.
    try:
        actual_digest = _compute_content_digest(bundle_dir)
    except ValueError as exc:
        _fail(
            f"Bundle integrity check failed: {exc}",
            EXIT_PUBLISH_FAIL,
        )
    if actual_digest != opts.content_sha256:
        _fail(
            "Bundle bytes do not match expected digest "
            f"(recomputed {actual_digest[:16]}…, "
            f"expected {opts.content_sha256[:16]}…). "
            "The bundle may have been modified after packaging.",
        )

    # --- Validate manifest inventory against actual bundle ---
    # Reuse the bundler's inventory routine to compare manifest records
    # with actual files.  A tampered manifest (empty files list, wrong
    # hashes, nonexistent entry point) is caught here BEFORE any deploy
    # command runs.
    manifest_files = manifest.get("files", [])
    actual_inventory = _collect_file_inventory(bundle_dir)
    # Exclude root manifest from comparison — consistent with digest.
    actual_by_path: dict[str, dict] = {
        f["path"]: f for f in actual_inventory
        if f["path"] != "preview-manifest.json"
    }
    manifest_by_path: dict[str, dict] = {}
    for mf in manifest_files:
        path = mf.get("path", "")
        if os.path.isabs(path) or ".." in Path(path).parts:
            _fail(
                f"Manifest file path is unsafe: {path!r}",
                EXIT_PUBLISH_FAIL,
            )
        if path in manifest_by_path:
            _fail(
                f"Manifest contains duplicate file path: {path!r}",
                EXIT_PUBLISH_FAIL,
            )
        manifest_by_path[path] = mf

    # Every manifest entry must exist in actual bundle with matching hash.
    for path, mf in manifest_by_path.items():
        if path not in actual_by_path:
            _fail(
                f"Manifest lists file not in bundle: {path!r}",
                EXIT_PUBLISH_FAIL,
            )
        if mf.get("sha256") != actual_by_path[path].get("sha256"):
            _fail(
                f"Manifest hash mismatch for {path!r}",
                EXIT_PUBLISH_FAIL,
            )

    # Every actual file (excluding root manifest) must be in manifest.
    for path in actual_by_path:
        if path not in manifest_by_path:
            _fail(
                f"Bundle file not in manifest: {path!r}",
                EXIT_PUBLISH_FAIL,
            )

    # Validate entry point exists as actual HTML file in bundle.
    entry = manifest.get("entry_point", "")
    if not entry:
        _fail("Manifest has no entry_point", EXIT_PUBLISH_FAIL)
    entry_path = bundle_dir / entry
    if not entry_path.is_file() or entry_path.is_symlink():
        _fail(
            f"Manifest entry_point {entry!r} does not exist as regular "
            "file in bundle",
            EXIT_PUBLISH_FAIL,
        )
    if Path(entry).suffix.lower() not in _HTML_EXTENSIONS:
        _fail(
            f"Manifest entry_point {entry!r} is not an HTML file",
            EXIT_PUBLISH_FAIL,
        )

    # Namespace uses SOURCE PR identity (pr_repo), not target_repo.
    namespace = _namespace_prefix(
        opts.pr_repo, opts.pr_number, opts.content_sha256,
    )

    # Guarded identity fields — deploy receipt cannot overwrite these.
    identity: dict[str, Any] = {
        "pr_repo": opts.pr_repo,
        "pr_number": int(opts.pr_number),
        "target_repo": opts.target_repo,
        "content_sha256_expected": opts.content_sha256,
        "namespace": namespace,
        "issue_key": manifest.get("issue_key", ""),
        "entry_point": manifest.get("entry_point", "index.html"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- Mode selection ---

    if opts.local_fixture:
        # TEST FIXTURE: local file copy.  Never treated as live deployment.
        site_dir = Path(opts.local_fixture).resolve()
        fixture_result = _local_fixture_publish(
            bundle_dir, site_dir, namespace, manifest,
        )
        receipt = {**identity, **fixture_result}
        print(json.dumps(receipt, indent=2))
        return EXIT_SUCCESS

    if opts.deploy_command:
        # PRODUCTION: execute project-owned deploy command.
        if not opts.site_url:
            _fail("--site-url is required when --deploy-command is used")
        approved_url = _validate_site_url(opts.site_url, opts.allow_test_http)

        cmd_path = Path(opts.deploy_command).resolve()
        if not cmd_path.is_file():
            _fail(f"Deploy command not found: {cmd_path}")
        if not os.access(cmd_path, os.X_OK):
            _fail(f"Deploy command not executable: {cmd_path}")

        try:
            result = subprocess.run(
                [str(cmd_path), str(bundle_dir), namespace,
                 opts.content_sha256, approved_url],
                capture_output=True, text=True, timeout=300,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            _fail("Deploy command timed out after 300s", EXIT_PUBLISH_FAIL)

        if result.returncode != 0:
            _fail(
                f"Deploy command failed (exit {result.returncode})",
                EXIT_PUBLISH_FAIL,
            )

        try:
            deploy_receipt = json.loads(result.stdout)
        except json.JSONDecodeError:
            _fail("Deploy command did not return valid JSON", EXIT_PUBLISH_FAIL)

        # Validate receipt has required fields.
        if deploy_receipt.get("status") != "published":
            _fail(
                f"Deploy command returned status "
                f"{deploy_receipt.get('status')!r}, expected 'published'",
                EXIT_PUBLISH_FAIL,
            )
        # Reject receipt URL outside approved site.
        receipt_url = deploy_receipt.get("url", "")
        if receipt_url and not receipt_url.rstrip("/").startswith(approved_url):
            _fail(
                f"Deploy receipt URL {receipt_url!r} is outside approved "
                f"site {approved_url!r}",
                EXIT_PUBLISH_FAIL,
            )

        # Validate receipt identity — returned fields must agree with expected.
        for key, expected in [
            ("namespace", namespace),
            ("pr_repo", opts.pr_repo),
            ("pr_number", int(opts.pr_number)),
            ("content_sha256", opts.content_sha256),
        ]:
            if key in deploy_receipt and deploy_receipt[key] != expected:
                _fail(
                    f"Deploy receipt {key}={deploy_receipt[key]!r} "
                    f"disagrees with expected {expected!r}",
                    EXIT_PUBLISH_FAIL,
                )

        # Merge receipt but GUARD identity — deploy cannot overwrite these.
        receipt = {**deploy_receipt, **identity}
        receipt["status"] = "deployed-unverified"

        # Served verification against APPROVED site URL (not receipt URL).
        vresult = _verify_served_url(approved_url, namespace, manifest)
        receipt["served_verification"] = vresult
        if vresult["verified"]:
            receipt["status"] = "published"
            # Canonical verified entry URL — never forward raw receipt URL.
            from urllib.parse import quote
            entry = manifest.get("entry_point", "index.html")
            receipt["verified_url"] = (
                f"{approved_url}/{namespace}/{quote(entry, safe='/')}"
            )

        # Remove raw receipt URL to prevent forwarding unverified link.
        receipt.pop("url", None)

        print(json.dumps(receipt, indent=2))
        return EXIT_SUCCESS if vresult["verified"] else EXIT_PUBLISH_FAIL

    # NO COMMAND CONFIGURED: awaiting-setup.
    receipt = {
        **identity,
        "status": "awaiting-setup",
        "reason": (
            "No deploy command configured.  The project owner must provide "
            "a deploy command that owns byte transport, whole-site assembly, "
            "and deployment.  Pass --deploy-command <path> to configure."
        ),
    }
    print(json.dumps(receipt, indent=2))
    return EXIT_SUCCESS


def cmd_verify(args: list[str]) -> int:
    """Verify published content matches expected digest."""
    import argparse
    p = argparse.ArgumentParser(prog="preview-publish verify")
    p.add_argument("--site-dir", required=True)
    p.add_argument("--namespace", required=True,
                   help="Publication namespace prefix")
    p.add_argument("--expected-digest", required=True)
    opts = p.parse_args(args)

    site_dir = Path(opts.site_dir).resolve()

    # --- Namespace safety validation ---
    # Reject absolute paths, traversal components, and symlink segments
    # within the site directory to prevent reads outside the site tree.
    if os.path.isabs(opts.namespace):
        _fail("Namespace must be a relative path", EXIT_ARG_ERROR)
    ns_parts = Path(opts.namespace).parts
    if ".." in ns_parts:
        _fail(
            "Namespace must not contain traversal components",
            EXIT_ARG_ERROR,
        )
    # Check each namespace component for symlinks before resolution.
    check_ns = site_dir
    for part in ns_parts:
        check_ns = check_ns / part
        if check_ns.is_symlink():
            _fail(
                f"Namespace path component is a symlink: {part!r}",
                EXIT_VERIFY_FAIL,
            )
    preview_dir = site_dir / opts.namespace
    # Verify resolved containment within site directory.
    try:
        preview_dir.resolve().relative_to(site_dir.resolve())
    except ValueError:
        _fail(
            "Namespace resolves outside site directory",
            EXIT_VERIFY_FAIL,
        )

    if not preview_dir.is_dir():
        _fail(f"Preview not found at {preview_dir}", EXIT_VERIFY_FAIL)

    manifest_path = preview_dir / "preview-manifest.json"
    if not manifest_path.is_file():
        _fail(f"No manifest at {manifest_path}", EXIT_VERIFY_FAIL)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Verify each file's per-file hash.
    mismatches: list[str] = []
    for file_entry in manifest.get("files", []):
        fpath = preview_dir / file_entry["path"]
        if not fpath.is_file():
            mismatches.append(f"missing: {file_entry['path']}")
            continue
        actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual_hash != file_entry.get("sha256", ""):
            mismatches.append(
                f"mismatch: {file_entry['path']} "
                f"expected={file_entry.get('sha256', '?')[:12]}… "
                f"actual={actual_hash[:12]}…"
            )

    # Verify aggregate digest using the canonical function.
    try:
        actual_digest = _compute_content_digest(preview_dir)
    except ValueError as exc:
        _fail(f"Content integrity check failed: {exc}", EXIT_VERIFY_FAIL)

    file_count = sum(
        1 for f in preview_dir.rglob("*")
        if f.is_file() and not f.is_symlink()
        and f != preview_dir / "preview-manifest.json"
    )

    result: dict[str, Any] = {
        "verified": actual_digest == opts.expected_digest and not mismatches,
        "expected_digest": opts.expected_digest,
        "actual_digest": actual_digest,
        "digest_match": actual_digest == opts.expected_digest,
        "per_file_mismatches": mismatches,
        "file_count": file_count,
    }

    print(json.dumps(result, indent=2))
    if not result["verified"]:
        return EXIT_VERIFY_FAIL
    return EXIT_SUCCESS


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: preview-publish.py {publish|verify} [args...]",
            file=sys.stderr,
        )
        return EXIT_ARG_ERROR
    cmd = sys.argv[1]
    if cmd == "publish":
        return cmd_publish(sys.argv[2:])
    if cmd == "verify":
        return cmd_verify(sys.argv[2:])
    _fail(f"Unknown subcommand: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
