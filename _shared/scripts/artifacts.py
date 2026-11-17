#!/usr/bin/env python3
"""Resolve workflow state in the main Git worktree, without creating or moving it.

CLI: artifacts.py [--repo PATH] [WORKFLOW [CONTEXT]]
     artifacts.py [--repo PATH] --path PATH
Prints an absolute state path; explicit non-state paths retain their meaning.
Exit 1 means unsafe/unavailable state; exit 2 is usage.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


class ArtifactError(ValueError):
    """Workflow state cannot safely be used."""


def worktrees(repo: str | Path | None = None) -> list[Path]:
    """Read Git's ordered, NUL-delimited worktree records (main is first)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo or Path.cwd()), "worktree", "list", "--porcelain", "-z"],
            capture_output=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ArtifactError(f"Cannot list Git worktrees: {error}") from error
    if result.returncode:
        raise ArtifactError("Artifact state requires an accessible non-bare Git repository")
    records = result.stdout.split(b"\0\0")
    paths = []
    for record in records:
        fields = record.split(b"\0")
        if b"bare" in fields:
            raise ArtifactError("Artifact state is not supported for a bare repository")
        for field in fields:
            if field.startswith(b"worktree "):
                paths.append(Path(os.fsdecode(field[len(b"worktree "):])))
    if not paths or not paths[0].is_dir():
        raise ArtifactError("Main worktree is unavailable; restore it before using artifact state")
    return paths


def _no_symlinks(path: Path, root: Path) -> Path:
    relative = path.relative_to(root)
    current = root
    for component in (None, *relative.parts):
        if component is not None:
            current = current / component
        if current.is_symlink():
            raise ArtifactError(f"Artifact paths must not use symlinks: {current}")
        if current.exists() and current != path and not current.is_dir():
            raise ArtifactError(f"Artifact parent is not a directory: {current}")
    return path


def _root(paths: list[Path]) -> Path:
    root = paths[0] / ".artifacts"
    _no_symlinks(root, root)
    if root.exists() and not root.is_dir():
        raise ArtifactError(f"Artifact root is not a directory: {root}")
    problems = []
    for worktree in paths[1:]:
        legacy = worktree / ".artifacts"
        if legacy.is_symlink() or (legacy.exists() and not legacy.is_dir()):
            problems.append(f"unsafe legacy artifact root: {legacy}")
        elif legacy.is_dir():
            def unreadable(error: OSError) -> None:
                raise ArtifactError(f"Cannot inspect legacy state: {error}") from error

            for directory, directories, files in os.walk(legacy, followlinks=False, onerror=unreadable):
                entries = files + [name for name in directories if (Path(directory) / name).is_symlink()]
                for name in entries:
                    source = Path(directory) / name
                    target = root / source.relative_to(legacy)
                    label = "legacy state"
                    if target.exists() or target.is_symlink():
                        label = "conflict/overlap"
                    problems.append(f"{label}: {source} -> {target}")
    if problems:
        raise ArtifactError(
            "Explicit artifact reconciliation required; nothing was moved or overwritten.\n"
            + "\n".join(problems)
            + "\nFollow _shared/recipes/resolve-artifacts.md before retrying."
        )
    return root


def artifact_root(repo: str | Path | None = None) -> Path:
    """Return canonical state root after checking all registered legacy locations."""
    return _root(worktrees(repo))


def artifact_directory(workflow: str, context: str | None = None,
                       repo: str | Path | None = None) -> Path:
    """Resolve a workflow directory, retaining the workflow's context naming."""
    components = [workflow] if context is None else [workflow, context]
    for component in components:
        if not component or component in (".", "..") or any(
            separator in component for separator in ("/", "\\", "\0")
        ):
            raise ArtifactError(f"Invalid artifact path component: {component!r}")
    root = artifact_root(repo)
    return _no_symlinks(root.joinpath(*components), root)


def canonical_path(path: str | Path, repo: str | Path | None = None) -> Path:
    """Canonicalize state paths only; explicit document/source paths stay unchanged.

    Relative .artifacts paths are repository-state shorthand, even in nested CWD.
    Absolute state paths must belong to a registered worktree. Other paths retain
    their caller-defined meaning, including published documents in a second repo.
    """
    path = Path(path)
    if ".artifacts" not in path.parts:
        return path
    if ".." in path.parts:
        raise ArtifactError(f"Unsafe artifact path: {path}")
    source = repo
    if source is None and path.is_absolute():
        marker = len(path.parts) - 1 - path.parts[::-1].index(".artifacts")
        source = Path(*path.parts[:marker])
        while not source.exists() and source.parent != source:
            source = source.parent
    paths = worktrees(source)
    root = _root(paths)
    if not path.is_absolute() and path.parts and path.parts[0] == ".artifacts":
        relative = Path(*path.parts[1:])
    elif path.is_absolute():
        relative = None
        for worktree in sorted(paths, key=lambda entry: len(entry.parts), reverse=True):
            try:
                relative = path.relative_to(worktree / ".artifacts")
                break
            except ValueError:
                continue
        if relative is None:
            return path
    else:
        return path
    if any(part in ("..",) or "\\" in part for part in relative.parts):
        raise ArtifactError(f"Unsafe artifact path: {path}")
    return _no_symlinks(root / relative, root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("workflow", nargs="?")
    parser.add_argument("context", nargs="?")
    args = parser.parse_args()
    if args.path is not None and args.workflow is not None:
        parser.error("--path cannot be combined with WORKFLOW")
    try:
        if args.path is not None:
            result = canonical_path(args.path, args.repo)
        elif args.workflow is not None:
            result = artifact_directory(args.workflow, args.context, args.repo)
        else:
            result = artifact_root(args.repo)
        print(result)
        return 0
    except (ArtifactError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
