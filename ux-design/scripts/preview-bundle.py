#!/usr/bin/env python3
"""Static review preview bundle builder for ux-design workflow.

Validates prototype output is self-contained and packages it into a
deployable static bundle with revision-scoped directory layout for
GitHub Pages or equivalent static hosting.

Subcommands:
  validate    Verify prototype directory is static-servable (no backend deps)
  package     Copy prototype output into a preview bundle with manifest
  manifest    Print JSON manifest of an existing bundle

Usage:
  preview-bundle.py validate --prototype-dir <path> [--mode standalone|workspace]
  preview-bundle.py package --prototype-dir <path> --output-dir <path>
                    --issue-key <key> --revision <rev>
                    [--mode standalone|workspace] [--entry-point <file>]
  preview-bundle.py manifest --bundle-dir <path>

Exit codes:
  0 -- success (validate: bundle is self-contained)
  1 -- argument or configuration error
  2 -- validation failure (runtime dependencies detected)
  3 -- packaging failure
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_VALIDATION_FAIL = 2
EXIT_PACKAGE_FAIL = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_ARG_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# Backend-dependency patterns in JavaScript / inline scripts.
# Each tuple: (compiled regex, human-readable description).
_BACKEND_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""\bfetch\s*\(\s*['"`]/(?!/)"""), "fetch() with absolute path"),
    (re.compile(r"""\bfetch\s*\(\s*['"`]https?://(?!cdn\.|unpkg\.com|cdnjs\.)"""),
     "fetch() to non-CDN URL"),
    (re.compile(r"\bXMLHttpRequest\b"), "XMLHttpRequest usage"),
    (re.compile(r"\baxios\s*[.(]"), "axios usage"),
    (re.compile(r"\blocalhost:\d+"), "localhost reference"),
    (re.compile(r"\b127\.0\.0\.1:\d+"), "loopback reference"),
    (re.compile(r"""['"`]https?://[^'"`]*?/api/"""), "API endpoint reference"),
]

# File extensions treated as HTML.
_HTML_EXTENSIONS = {".html", ".htm"}

# File extensions treated as JavaScript.
_JS_EXTENSIONS = {".js", ".mjs", ".jsx", ".ts", ".tsx"}

# Static asset extensions (copied but not scanned).
_ASSET_EXTENSIONS = {
    ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff",
    ".woff2", ".ttf", ".eot", ".webp", ".avif", ".map", ".json",
}

# Maximum file size to scan for backend patterns (2 MiB).
_MAX_SCAN_BYTES = 2 * 1024 * 1024


def _resolve_content_dir(prototype_dir: Path, mode: str) -> Path | None:
    """Return the directory containing servable static content.

    For standalone mode, looks for ``prototype/`` under the prototype dir.
    For workspace mode, looks for pre-built static output directories
    (``dist/``, ``build/``, ``out/``, ``public/``) under ``code/``.
    Returns None when no static content directory is found.
    """
    if mode == "standalone":
        candidate = prototype_dir / "prototype"
        if candidate.is_dir() and not candidate.is_symlink():
            return candidate
        # Fallback: the prototype dir itself may contain HTML.
        html_files = list(prototype_dir.glob("*.html"))
        if html_files:
            return prototype_dir
        return None

    # workspace mode
    code_dir = prototype_dir / "code"
    if not code_dir.is_dir():
        return None

    for subdir in ("dist", "build", "out", "public", "exports"):
        candidate = code_dir / subdir
        if candidate.is_dir() and list(candidate.glob("*.html")):
            return candidate

    # Check if code/ itself has HTML files (single-page prototype).
    if list(code_dir.glob("*.html")):
        return code_dir

    return None


def _find_entry_point(content_dir: Path, explicit: str | None = None) -> Path | None:
    """Locate the HTML entry point within the content directory."""
    if explicit:
        candidate = content_dir / explicit
        if candidate.is_file():
            return candidate
        return None

    for name in ("index.html", "index.htm"):
        candidate = content_dir / name
        if candidate.is_file():
            return candidate

    # Fall back to first HTML file found.
    html_files = sorted(content_dir.glob("**/*.html"))
    return html_files[0] if html_files else None


def _scan_file_for_dependencies(
    filepath: Path,
) -> list[dict[str, str]]:
    """Scan a single file for backend dependency indicators.

    Returns a list of finding dicts with ``pattern``, ``file``, and
    ``line`` keys.
    """
    findings: list[dict[str, str]] = []
    try:
        size = filepath.stat().st_size
        if size > _MAX_SCAN_BYTES:
            return findings
        text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    for line_num, line in enumerate(text.splitlines(), 1):
        for pattern, desc in _BACKEND_PATTERNS:
            if pattern.search(line):
                findings.append({
                    "pattern": desc,
                    "file": str(filepath),
                    "line": str(line_num),
                })
    return findings


def _scan_directory(content_dir: Path) -> list[dict[str, str]]:
    """Scan all HTML and JS files in a directory tree for backend deps."""
    findings: list[dict[str, str]] = []
    for filepath in sorted(content_dir.rglob("*")):
        if filepath.is_symlink() or not filepath.is_file():
            continue
        ext = filepath.suffix.lower()
        if ext in _HTML_EXTENSIONS or ext in _JS_EXTENSIONS:
            findings.extend(_scan_file_for_dependencies(filepath))
    return findings


def _collect_file_inventory(
    content_dir: Path,
) -> list[dict[str, str]]:
    """Build a file inventory of the content directory."""
    inventory: list[dict[str, str]] = []
    for filepath in sorted(content_dir.rglob("*")):
        if not filepath.is_file() or filepath.is_symlink():
            continue
        ext = filepath.suffix.lower()
        if ext in _HTML_EXTENSIONS:
            category = "html"
        elif ext in _JS_EXTENSIONS:
            category = "script"
        elif ext in {".css"}:
            category = "style"
        elif ext in _ASSET_EXTENSIONS:
            category = "asset"
        else:
            category = "other"
        rel = filepath.relative_to(content_dir)
        inventory.append({
            "path": rel.as_posix(),
            "category": category,
            "size_bytes": str(filepath.stat().st_size),
        })
    return inventory


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """Validate that a prototype directory produces a static bundle.

    Prints a JSON report to stdout with ``valid``, ``entry_point``,
    ``content_dir``, ``findings``, and ``file_count`` fields.
    """
    prototype_dir = Path(args.prototype_dir).resolve()
    mode = args.mode

    if not prototype_dir.is_dir():
        fail(f"validate: prototype directory does not exist: {prototype_dir}")

    content_dir = _resolve_content_dir(prototype_dir, mode)
    if content_dir is None:
        report: dict[str, Any] = {
            "valid": False,
            "reason": "no_static_content",
            "message": (
                f"No static content found in {mode} prototype. "
                "Screenshot fallback recommended."
            ),
            "content_dir": None,
            "entry_point": None,
            "findings": [],
            "file_count": 0,
        }
        print(json.dumps(report, indent=2))
        return EXIT_VALIDATION_FAIL

    entry_point = _find_entry_point(content_dir, args.entry_point)
    findings = _scan_directory(content_dir)
    file_count = sum(1 for f in content_dir.rglob("*") if f.is_file())

    is_valid = len(findings) == 0 and entry_point is not None
    reason = "ok"
    message = "Prototype is self-contained and static-servable."
    if entry_point is None:
        reason = "no_entry_point"
        message = "No HTML entry point found."
        is_valid = False
    elif findings:
        reason = "backend_dependencies"
        message = (
            f"Found {len(findings)} backend dependency indicator(s). "
            "The prototype may require a live backend to function. "
            "Review the findings and consider screenshot fallback."
        )

    report = {
        "valid": is_valid,
        "reason": reason,
        "message": message,
        "content_dir": str(content_dir),
        "entry_point": (
            entry_point.relative_to(content_dir).as_posix()
            if entry_point
            else None
        ),
        "findings": findings,
        "file_count": file_count,
    }
    print(json.dumps(report, indent=2))
    return EXIT_SUCCESS if is_valid else EXIT_VALIDATION_FAIL


# ---------------------------------------------------------------------------
# Subcommand: package
# ---------------------------------------------------------------------------

def cmd_package(args: argparse.Namespace) -> int:
    """Package prototype output into a deployable preview bundle.

    Creates a directory at ``output_dir/previews/{issue_key}/{revision}/``
    containing the static content and a ``preview-manifest.json``.
    """
    prototype_dir = Path(args.prototype_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    issue_key = args.issue_key
    revision = args.revision
    mode = args.mode

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", issue_key):
        fail("package: invalid issue key format")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", revision):
        fail("package: invalid revision format")
    if not prototype_dir.is_dir():
        fail(f"package: prototype directory does not exist: {prototype_dir}")

    content_dir = _resolve_content_dir(prototype_dir, mode)
    if content_dir is None:
        fail(
            "package: no static content found. "
            "Run validate first to check preview feasibility.",
            EXIT_PACKAGE_FAIL,
        )

    entry_point = _find_entry_point(content_dir, args.entry_point)
    if entry_point is None:
        fail("package: no HTML entry point found.", EXIT_PACKAGE_FAIL)

    # Build the namespaced bundle directory.
    bundle_dir = output_dir / "previews" / issue_key / revision
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Copy content tree, skipping symlinks.
    for src_file in sorted(content_dir.rglob("*")):
        if src_file.is_symlink() or not src_file.is_file():
            continue
        rel = src_file.relative_to(content_dir)
        dest = bundle_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)

    # Collect inventory and write manifest.
    inventory = _collect_file_inventory(bundle_dir)
    manifest: dict[str, Any] = {
        "issue_key": issue_key,
        "revision": revision,
        "mode": mode,
        "entry_point": entry_point.relative_to(content_dir).as_posix(),
        "file_count": len(inventory),
        "files": inventory,
        "mocked_components": [],
        "notes": (
            "Self-contained static preview. "
            "No runtime backend required for review."
        ),
    }

    # Read prototype-notes.md for mock inventory if available.
    notes_file = prototype_dir / "prototype-notes.md"
    if notes_file.is_file():
        try:
            notes_text = notes_file.read_text(encoding="utf-8", errors="replace")
            mocked = []
            in_page_context = False
            for line in notes_text.splitlines():
                if "## Page Context" in line:
                    in_page_context = True
                    continue
                if in_page_context and line.startswith("## "):
                    break
                if in_page_context and "| mocked" in line.lower():
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2:
                        mocked.append({
                            "section": parts[0],
                            "status": "mocked",
                            "source": parts[2] if len(parts) > 2 else "unknown",
                        })
            manifest["mocked_components"] = mocked
        except OSError:
            pass

    manifest_path = bundle_dir / "preview-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    info(f"Bundle created: {bundle_dir}")
    info(f"Entry point: {manifest['entry_point']}")
    info(f"Files: {manifest['file_count']}")
    print(json.dumps({
        "bundle_dir": str(bundle_dir),
        "entry_point": manifest["entry_point"],
        "file_count": manifest["file_count"],
        "manifest_path": str(manifest_path),
    }, indent=2))
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: manifest
# ---------------------------------------------------------------------------

def cmd_manifest(args: argparse.Namespace) -> int:
    """Print the manifest of an existing preview bundle."""
    bundle_dir = Path(args.bundle_dir).resolve()
    manifest_path = bundle_dir / "preview-manifest.json"

    if not manifest_path.is_file():
        fail(f"manifest: no preview-manifest.json found in {bundle_dir}")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        fail(f"manifest: failed to read manifest: {exc}")

    print(json.dumps(data, indent=2, ensure_ascii=False))
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommand parsers."""
    parser = argparse.ArgumentParser(
        description="Static review preview bundle builder for ux-design.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # -- validate --
    p_validate = subparsers.add_parser(
        "validate",
        help="Verify prototype directory is static-servable",
    )
    p_validate.add_argument(
        "--prototype-dir", required=True,
        help="Path to the 03-prototype directory",
    )
    p_validate.add_argument(
        "--mode", choices=["standalone", "workspace"], default="standalone",
        help="Prototype mode (default: standalone)",
    )
    p_validate.add_argument(
        "--entry-point", default=None,
        help="Explicit entry point filename (default: auto-detect)",
    )

    # -- package --
    p_package = subparsers.add_parser(
        "package",
        help="Package prototype output into a preview bundle",
    )
    p_package.add_argument(
        "--prototype-dir", required=True,
        help="Path to the 03-prototype directory",
    )
    p_package.add_argument(
        "--output-dir", required=True,
        help="Base output directory for the preview bundle",
    )
    p_package.add_argument(
        "--issue-key", required=True,
        help="Jira issue key for namespace scoping",
    )
    p_package.add_argument(
        "--revision", required=True,
        help="Prototype revision identifier (e.g., iteration-1)",
    )
    p_package.add_argument(
        "--mode", choices=["standalone", "workspace"], default="standalone",
        help="Prototype mode (default: standalone)",
    )
    p_package.add_argument(
        "--entry-point", default=None,
        help="Explicit entry point filename (default: auto-detect)",
    )

    # -- manifest --
    p_manifest = subparsers.add_parser(
        "manifest",
        help="Print JSON manifest of an existing bundle",
    )
    p_manifest.add_argument(
        "--bundle-dir", required=True,
        help="Path to the preview bundle directory",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUBCOMMAND_MAP = {
    "validate": cmd_validate,
    "package": cmd_package,
    "manifest": cmd_manifest,
}


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return EXIT_ARG_ERROR

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if handler is None:
        fail(f"Unknown subcommand: {args.subcommand}")

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
