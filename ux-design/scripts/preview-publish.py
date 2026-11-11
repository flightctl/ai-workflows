#!/usr/bin/env python3
"""Preview publisher wrapper for the ux-design preview phase.

A small UX-specific project-approved PUBLISHER COMMAND wrapper.  It does
NOT perform deployment itself — it delegates to a project-owned deploy
command.  When no deploy command is configured, it returns awaiting-setup.

Contract:
  publish   Invoke the configured deploy command (or report awaiting-setup)
  verify    Check published content against its manifest

The deploy command receives:
  argv[1]  bundle directory (absolute path)
  argv[2]  namespace prefix (e.g. previews/org/repo/pr-42/a1b2c3d4)
  argv[3]  expected content SHA-256

It must print a JSON receipt to stdout with at minimum:
  {"status": "published", "url": "...", "content_sha256": "..."}

For testing, --local-fixture <site-dir> provides a built-in adapter
that copies into a local directory.  Its receipt is clearly marked
"published-local" and must never be treated as live deployment.

Usage:
  preview-publish.py publish --bundle-dir <path> --pr-repo <owner/repo>
      --pr-number <N> --content-sha256 <hash> --target-repo <owner/repo>
      [--deploy-command <path>] [--local-fixture <site-dir>]
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


def _verify_served_url(
    base_url: str, namespace: str, manifest: dict[str, Any],
) -> dict[str, Any]:
    """Verify content served at *base_url/namespace/* matches *manifest*.

    Uses HTTP(S) GET for each file.  Returns a dict with ``verified``
    bool and ``errors`` list.  Loopback HTTP is used in tests; approved
    HTTPS URLs in production.
    """
    import urllib.error
    import urllib.request

    prefix = f"{base_url.rstrip('/')}/{namespace}"
    errors: list[str] = []

    # Verify served manifest.
    try:
        murl = f"{prefix}/preview-manifest.json"
        with urllib.request.urlopen(murl, timeout=10) as resp:
            served = json.loads(resp.read())
            if served.get("content_sha256") != manifest.get("content_sha256"):
                errors.append("served manifest content_sha256 differs")
    except Exception as exc:
        return {"verified": False, "errors": [f"manifest unreachable: {exc}"]}

    # Verify per-file hashes.
    for fe in manifest.get("files", []):
        furl = f"{prefix}/{fe['path']}"
        try:
            with urllib.request.urlopen(furl, timeout=10) as resp:
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

    # Compute published content digest (excluding manifest).
    content_files = sorted(
        f for f in dest.rglob("*")
        if f.is_file() and not f.is_symlink()
        and f.name != "preview-manifest.json"
    )
    hasher = hashlib.sha256()
    for fp in content_files:
        rel = fp.relative_to(dest).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(fp.read_bytes())
    published_digest = hasher.hexdigest()

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

    return {
        "status": "published-local",
        "content_sha256": published_digest,
        "manifest_sha256": manifest.get("content_sha256", ""),
        "digest_match": published_digest == manifest.get("content_sha256", ""),
        "namespace": namespace,
        "file_count": len(content_files),
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
    p.add_argument("--local-fixture", default=None, metavar="SITE_DIR",
                   help="TEST ONLY: local file copy to site directory")
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
        cmd_path = Path(opts.deploy_command).resolve()
        if not cmd_path.is_file():
            _fail(f"Deploy command not found: {cmd_path}")
        if not os.access(cmd_path, os.X_OK):
            _fail(f"Deploy command not executable: {cmd_path}")

        try:
            result = subprocess.run(
                [str(cmd_path), str(bundle_dir), namespace, opts.content_sha256],
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
        deploy_url = deploy_receipt.get("url", "")
        if not deploy_url:
            _fail("Deploy receipt missing 'url' field", EXIT_PUBLISH_FAIL)

        # Merge receipt but GUARD identity — deploy cannot overwrite these.
        receipt = {**deploy_receipt, **identity}
        receipt["deploy_url"] = deploy_url
        receipt["status"] = "deployed-unverified"

        # Served verification against the returned URL.
        vresult = _verify_served_url(deploy_url, namespace, manifest)
        receipt["served_verification"] = vresult
        if vresult["verified"]:
            receipt["status"] = "published"
        else:
            receipt["status"] = "deployed-unverified"

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
    preview_dir = site_dir / opts.namespace

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

    # Verify aggregate digest.
    content_files = sorted(
        f for f in preview_dir.rglob("*")
        if f.is_file() and not f.is_symlink()
        and f.name != "preview-manifest.json"
    )
    hasher = hashlib.sha256()
    for fp in content_files:
        rel = fp.relative_to(preview_dir).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(fp.read_bytes())
    actual_digest = hasher.hexdigest()

    result: dict[str, Any] = {
        "verified": actual_digest == opts.expected_digest and not mismatches,
        "expected_digest": opts.expected_digest,
        "actual_digest": actual_digest,
        "digest_match": actual_digest == opts.expected_digest,
        "per_file_mismatches": mismatches,
        "file_count": len(content_files),
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
