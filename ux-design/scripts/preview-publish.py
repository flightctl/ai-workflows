#!/usr/bin/env python3
"""Minimal preview publisher — local fixture for the ux-design preview phase.

Assembles a preview bundle into a site directory while preserving existing
content (docs, other PR previews).  Returns a JSON receipt with content
identity.  This is a LOCAL development/test fixture, not a live Pages
deployment.

Subcommands:
  publish   Copy a packaged bundle into a site directory, return receipt
  verify    Check a published bundle's content against its manifest

Usage:
  preview-publish.py publish --bundle-dir <path> --site-dir <path>
                     --pr-url <url> --target-repo <owner/repo>
  preview-publish.py verify  --site-dir <path> --issue-key <key>
                     --revision <rev> --expected-digest <sha256>

Exit codes:
  0 -- success
  1 -- argument or configuration error
  2 -- verification failure (content mismatch)
  3 -- publish failure
"""

from __future__ import annotations

import hashlib
import json
import shutil
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


def _compute_digest(directory: Path) -> str:
    """SHA-256 over sorted file paths and contents — matches preview-bundle.py."""
    hasher = hashlib.sha256()
    for filepath in sorted(directory.rglob("*")):
        if not filepath.is_file() or filepath.is_symlink():
            continue
        rel = filepath.relative_to(directory).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(filepath.read_bytes())
    return hasher.hexdigest()


def cmd_publish(args: list[str]) -> int:
    """Publish a bundle into a site directory, preserving existing content."""
    import argparse
    p = argparse.ArgumentParser(prog="preview-publish publish")
    p.add_argument("--bundle-dir", required=True)
    p.add_argument("--site-dir", required=True)
    p.add_argument("--pr-url", required=True)
    p.add_argument("--target-repo", required=True)
    opts = p.parse_args(args)

    bundle_dir = Path(opts.bundle_dir).resolve()
    site_dir = Path(opts.site_dir).resolve()

    manifest_path = bundle_dir / "preview-manifest.json"
    if not manifest_path.is_file():
        _fail(f"No preview-manifest.json in {bundle_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issue_key = manifest.get("issue_key", "")
    revision = manifest.get("revision", "")
    if not issue_key or not revision:
        _fail("Manifest missing issue_key or revision")

    # Destination preserves namespace: site/previews/{issue_key}/{revision}/
    dest = site_dir / "previews" / issue_key / revision
    if dest.exists():
        _fail(
            f"Destination already exists: {dest}. "
            "Use a different revision to preserve existing content.",
            EXIT_PUBLISH_FAIL,
        )

    # Verify existing site content is preserved (list before).
    existing_before = set()
    if site_dir.exists():
        existing_before = {
            str(f.relative_to(site_dir))
            for f in site_dir.rglob("*") if f.is_file()
        }

    # Copy bundle content into namespaced destination.
    dest.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(bundle_dir.rglob("*")):
        if not src_file.is_file() or src_file.is_symlink():
            continue
        rel = src_file.relative_to(bundle_dir)
        dst_file = dest / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

    # Verify content identity matches manifest.
    # Compute digest over content files only (exclude the manifest itself
    # from the digest comparison, matching preview-bundle.py's convention).
    content_files = sorted(
        f for f in dest.rglob("*")
        if f.is_file() and not f.is_symlink()
        and f.name != "preview-manifest.json"
    )
    content_hasher = hashlib.sha256()
    for filepath in content_files:
        rel = filepath.relative_to(dest).as_posix()
        content_hasher.update(rel.encode("utf-8"))
        content_hasher.update(filepath.read_bytes())
    published_digest = content_hasher.hexdigest()

    # Verify existing content still intact.
    existing_after = set()
    if site_dir.exists():
        existing_after = {
            str(f.relative_to(site_dir))
            for f in site_dir.rglob("*") if f.is_file()
            if not str(f.relative_to(site_dir)).startswith(
                f"previews/{issue_key}/{revision}"
            )
        }

    if existing_before != existing_after:
        missing = existing_before - existing_after
        _fail(
            f"Site preservation violated: {len(missing)} existing file(s) "
            f"lost during publish: {sorted(missing)[:5]}",
            EXIT_PUBLISH_FAIL,
        )

    receipt: dict[str, Any] = {
        "status": "published-local",
        "issue_key": issue_key,
        "revision": revision,
        "entry_point": manifest.get("entry_point", "index.html"),
        "content_sha256": published_digest,
        "manifest_sha256": manifest.get("content_sha256", ""),
        "digest_match": published_digest == manifest.get("content_sha256", ""),
        "pr_url": opts.pr_url,
        "target_repo": opts.target_repo,
        "site_dir": str(site_dir),
        "preview_path": f"previews/{issue_key}/{revision}",
        "file_count": len(content_files),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "LOCAL fixture — not a live Pages deployment",
    }

    print(json.dumps(receipt, indent=2))
    return EXIT_SUCCESS


def cmd_verify(args: list[str]) -> int:
    """Verify published content matches expected digest."""
    import argparse
    p = argparse.ArgumentParser(prog="preview-publish verify")
    p.add_argument("--site-dir", required=True)
    p.add_argument("--issue-key", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--expected-digest", required=True)
    opts = p.parse_args(args)

    site_dir = Path(opts.site_dir).resolve()
    preview_dir = site_dir / "previews" / opts.issue_key / opts.revision

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
    content_hasher = hashlib.sha256()
    for filepath in content_files:
        rel = filepath.relative_to(preview_dir).as_posix()
        content_hasher.update(rel.encode("utf-8"))
        content_hasher.update(filepath.read_bytes())
    actual_digest = content_hasher.hexdigest()

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
        print("Usage: preview-publish.py {publish|verify} [args...]",
              file=sys.stderr)
        return EXIT_ARG_ERROR
    cmd = sys.argv[1]
    if cmd == "publish":
        return cmd_publish(sys.argv[2:])
    if cmd == "verify":
        return cmd_verify(sys.argv[2:])
    _fail(f"Unknown subcommand: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
