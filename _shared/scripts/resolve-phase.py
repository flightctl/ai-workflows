#!/usr/bin/env python3
"""Phase override resolution for ai-workflows.

Resolves the skill file for a workflow phase, checking for a
project-level override before falling back to the workflow's built-in
default.  This replaces the ~200-token AI recipe evaluation on every
phase dispatch with a deterministic file-existence check.

Usage:
  resolve-phase.py [--builtin-only] <WORKFLOW> <PHASE_FILE>

Arguments:
  WORKFLOW        Workflow name (e.g., bugfix, design, docs-writer)
  PHASE_FILE      Skill filename to resolve (e.g., assess.md,
                  gather-context.md).  The .md extension is optional;
                  bare names like "assess" are normalized to "assess.md".

Options:
  --builtin-only  Skip the project-override check and resolve directly
                  to the built-in default.  Use after validation rejects
                  an override so re-resolution cannot select it again.

Output:
  Prints the resolved path to stdout.
  If an override exists at .workflows/{WORKFLOW}/skills/{PHASE_FILE}
  (relative to the current directory), prints that path.
  Otherwise prints the built-in default path.
  With --builtin-only, always prints the built-in default path.

Exit codes:
  0 -- success (path printed to stdout)
  1 -- resolution failure (built-in not found, empty file, unsafe path)
  2 -- invalid arguments (from argparse)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_RESOLUTION_ERROR = 1
# argparse uses exit code 2 for usage errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_RESOLUTION_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# Allow lowercase letters, digits, hyphens, and dots — no slashes,
# backslashes, path separators, or traversal sequences.
_SAFE_COMPONENT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _validate_path_component(value: str, label: str) -> None:
    """Reject path traversal and unsafe characters in a path component.

    Args:
        value: The path component to validate.
        label: Human-readable name for error messages (e.g., 'workflow').

    Raises:
        SystemExit: If the value is unsafe.
    """
    if not value:
        fail(f"{label} must not be empty")

    if ".." in value:
        fail(f"{label} must not contain '..': {value}")

    if value.startswith(("/", "\\")):
        fail(f"{label} must not be an absolute path: {value}")

    if "/" in value or "\\" in value:
        fail(f"{label} must not contain path separators: {value}")

    if not _SAFE_COMPONENT.match(value):
        fail(f"{label} contains unsafe characters: {value}")


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------

def resolve_phase(
    workflow: str,
    phase_file: str,
    *,
    builtin_only: bool = False,
) -> str:
    """Resolve the skill file path for a workflow phase.

    Checks for a project-level override at
    ``.workflows/{workflow}/skills/{phase_file}`` relative to the current
    working directory.  If the override exists, returns that path.
    Otherwise returns the built-in default path, resolved relative to
    this script's location in the ai-workflows repository.

    When ``builtin_only`` is True, skips the override check entirely and
    resolves directly to the built-in default.  Use this after validation
    rejects an override so re-resolution cannot select it again.

    Args:
        workflow: Workflow name (e.g., 'bugfix', 'design').
        phase_file: Skill filename (e.g., 'assess.md' or 'assess').
        builtin_only: If True, skip override check (default: False).

    Returns:
        The resolved file path as a string.

    Raises:
        SystemExit: If a path component is unsafe, the built-in fallback
            cannot be located, or the built-in file is empty/unreadable.
    """
    # Normalize bare phase names (e.g. "code" -> "code.md")
    if not phase_file.endswith(".md"):
        phase_file += ".md"

    # Validate inputs against path traversal
    _validate_path_component(workflow, "workflow")
    _validate_path_component(phase_file, "phase_file")

    # Check for project-level override (unless --builtin-only)
    if not builtin_only:
        override_path = Path(".workflows") / workflow / "skills" / phase_file
        if override_path.is_file():
            # Symlink-escape guard: canonicalize all paths and verify the
            # resolved override stays within the project root's override
            # directory.  This prevents a symlink in .workflows/ from
            # pointing outside the project and crossing the trust boundary.
            project_root = Path.cwd().resolve()
            override_root = (
                project_root / ".workflows" / workflow / "skills"
            ).resolve()
            canonical = override_path.resolve()

            if not (
                str(override_root).startswith(str(project_root) + os.sep)
                and str(canonical).startswith(str(override_root) + os.sep)
            ):
                fail(
                    f"Override escapes project boundary: "
                    f"{workflow}/{phase_file}",
                )

            info(f"Using project override: {workflow}/{phase_file}.")
            return str(override_path)

    # Fall back to built-in default
    # This script is at _shared/scripts/resolve-phase.py
    # Built-in phases are at {WORKFLOW}/skills/{PHASE_FILE} from repo root
    # Relative to this script: ../../{WORKFLOW}/skills/{PHASE_FILE}
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    builtin_path = repo_root / workflow / "skills" / phase_file

    if not builtin_path.is_file():
        fail(f"Built-in phase not found: {workflow}/skills/{phase_file}")

    # Verify the file is readable and non-empty
    try:
        content = builtin_path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(
            f"Built-in phase not readable: {workflow}/skills/{phase_file}"
            f" ({exc})",
        )
    if not content.strip():
        fail(
            f"Built-in phase is empty: {workflow}/skills/{phase_file}",
        )

    return str(builtin_path)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Resolve a workflow phase skill file, checking for "
                    "project-level overrides before falling back to the "
                    "built-in default.",
    )
    parser.add_argument(
        "--builtin-only",
        action="store_true",
        default=False,
        help="Skip override check; resolve directly to built-in default",
    )
    parser.add_argument(
        "workflow",
        help="Workflow name (e.g., bugfix, design, docs-writer)",
    )
    parser.add_argument(
        "phase_file",
        help="Skill filename to resolve (e.g., assess.md, "
             "gather-context.md). The .md extension is optional.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Parse arguments and resolve the phase file path."""
    parser = build_parser()
    args = parser.parse_args(argv)

    resolved = resolve_phase(
        args.workflow,
        args.phase_file,
        builtin_only=args.builtin_only,
    )
    print(resolved)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
