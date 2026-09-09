#!/usr/bin/env python3
"""Deterministic publish operations for ai-workflows.

Provides reusable subcommands for the publish/PR/MR phase of multiple
workflows (bugfix, implement, e2e, prd, design, docs-writer). Each
subcommand handles one discrete, deterministic operation -- the calling
skill file retains ownership of AI-dependent work (PR body generation,
cross-cutting review, user confirmation prompts).

Subcommands:
  preflight       Pre-flight checks (auth, branch, uncommitted changes)
  push            Push a branch to a remote
  check-existing  Check whether a PR/MR already exists for a branch
  create-pr       Create a GitHub pull request via gh CLI
  create-mr       Create a GitLab merge request via glab CLI
  save-metadata   Write publish-metadata.json

Usage:
  publish.py preflight [--platform github|gitlab]
  publish.py push --remote <name> --branch <branch>
  publish.py check-existing --repo <owner/repo> --head <branch>
             [--platform github|gitlab]
  publish.py create-pr --repo <owner/repo> --base <branch> --head <ref>
             --title <title> [--body-file <path>] [--body <text>]
             [--draft] [--labels <csv>]
  publish.py create-mr --project <path> --source <branch>
             --target <branch> --title <title> [--description <text>]
             [--desc-file <path>] [--draft] [--head <project>]
  publish.py save-metadata --file <path> [--pair key=value ...]

Exit codes:
  0 -- success
  1 -- missing argument or configuration error
  3 -- push failed
  4 -- PR/MR creation failed
  5 -- existing PR/MR found (check-existing only; prints JSON on stdout)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1
EXIT_PUSH_FAIL = 3
EXIT_CREATE_FAIL = 4
EXIT_EXISTING_FOUND = 5


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


def run(
    cmd: list[str],
    *,
    capture: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with text output."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
    )


# ---------------------------------------------------------------------------
# Subcommand: preflight
# ---------------------------------------------------------------------------

def cmd_preflight(args: argparse.Namespace) -> int:
    """Run pre-flight checks: auth, branch, and working-tree cleanliness.

    Prints a JSON object on stdout with auth_ok, auth_user, branch,
    has_uncommitted, has_staged, has_untracked, and platform fields.
    """
    platform = args.platform

    if platform not in ("github", "gitlab"):
        fail(f"preflight: invalid platform: {platform} "
             f"(expected github or gitlab)")

    auth_ok = False
    auth_user = ""

    # -- Auth check --
    if platform == "github":
        result = run(["gh", "auth", "status"])
        if result.returncode == 0:
            auth_ok = True
            r = run(["gh", "api", "user", "--jq", ".login"])
            if r.returncode == 0 and r.stdout.strip():
                auth_user = r.stdout.strip()
            else:
                # GitHub App / bot -- try installation endpoint
                r = run([
                    "gh", "api", "/installation/repositories",
                    "--jq", ".repositories[0].owner.login",
                ])
                if r.returncode == 0 and r.stdout.strip():
                    auth_user = r.stdout.strip()
    else:  # gitlab
        result = run(["glab", "auth", "status"])
        if result.returncode == 0:
            auth_ok = True
            r = run(["glab", "api", "user", "--jq", ".username"])
            if r.returncode == 0 and r.stdout.strip():
                auth_user = r.stdout.strip()

    # -- Branch --
    r = run(["git", "branch", "--show-current"])
    branch = r.stdout.strip() if r.returncode == 0 else ""

    # -- Remote --
    remote = ""
    r = run(["git", "remote"])
    if r.returncode == 0:
        remotes = r.stdout.strip().splitlines()
        if remotes:
            # Prefer "fork" if it exists, else first remote
            remote = "fork" if "fork" in remotes else remotes[0]

    # -- Uncommitted changes --
    has_uncommitted = run(["git", "diff", "--quiet"]).returncode != 0
    has_staged = run(["git", "diff", "--cached", "--quiet"]).returncode != 0

    r = run(["git", "ls-files", "--others", "--exclude-standard"])
    has_untracked = bool(r.returncode == 0 and r.stdout.strip())

    output: dict[str, Any] = {
        "auth_ok": auth_ok,
        "auth_user": auth_user,
        "branch": branch,
        "remote": remote,
        "has_uncommitted": has_uncommitted,
        "has_staged": has_staged,
        "has_untracked": has_untracked,
        "platform": platform,
    }

    print(json.dumps(output, indent=2))
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: push
# ---------------------------------------------------------------------------

def cmd_push(args: argparse.Namespace) -> int:
    """Push a branch to the specified remote with upstream tracking (-u)."""
    remote = args.remote
    branch = args.branch

    if not remote:
        fail("Missing required argument: --remote")
    if not branch:
        fail("Missing required argument: --branch")

    # Verify the remote exists
    r = run(["git", "remote", "get-url", remote])
    if r.returncode != 0:
        remotes_r = run(["git", "remote"])
        available = remotes_r.stdout.strip().replace("\n", " ") if remotes_r.returncode == 0 else "(none)"
        fail(f"push: remote '{remote}' does not exist. "
             f"Available remotes: {available}", EXIT_PUSH_FAIL)

    info(f"Pushing {branch} to {remote}...")
    result = run(["git", "push", "-u", remote, branch], capture=False)
    if result.returncode != 0:
        fail(f"push: git push failed (remote={remote}, branch={branch})",
             EXIT_PUSH_FAIL)

    info(f"Push successful: {remote}/{branch}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: check-existing
# ---------------------------------------------------------------------------

def cmd_check_existing(args: argparse.Namespace) -> int:
    """Check whether an open PR (GitHub) or MR (GitLab) already exists.

    Exit code 0 if NO existing PR/MR found (safe to create one).
    Exit code 5 if an existing PR/MR IS found (details as JSON on stdout).
    """
    repo = args.repo
    head = args.head
    platform = args.platform

    if not repo:
        fail("Missing required argument: --repo")
    if not head:
        fail("Missing required argument: --head")

    if platform == "github":
        return _check_existing_github(repo, head)
    elif platform == "gitlab":
        return _check_existing_gitlab(repo, head)
    else:
        fail(f"check-existing: invalid platform: {platform}")
    return EXIT_ARG_ERROR  # unreachable; satisfies type checker


def _check_existing_github(repo: str, head: str) -> int:
    """GitHub check-existing: use gh pr list with headRepositoryOwner filtering."""
    if ":" in head:
        # owner:branch format -- gh pr list --head does not support this
        # syntax.  Search by branch name and filter by head repo owner.
        head_owner, head_branch = head.split(":", 1)
        r = run([
            "gh", "pr", "list",
            "--repo", repo,
            "--head", head_branch,
            "--json", "number,url,headRepositoryOwner",
        ])
        if r.returncode != 0:
            fail("check-existing: GitHub API query failed. "
                 "Check gh auth status.")

        try:
            prs = json.loads(r.stdout) if r.stdout.strip() else []
        except json.JSONDecodeError:
            fail("check-existing: failed to parse GitHub API response")
            return EXIT_ARG_ERROR  # unreachable

        # Filter by headRepositoryOwner
        matching = [
            pr for pr in prs
            if isinstance(pr.get("headRepositoryOwner"), dict)
            and pr["headRepositoryOwner"].get("login") == head_owner
        ]
        if matching:
            result = {"number": matching[0]["number"], "url": matching[0]["url"]}
            print(json.dumps(result, indent=2))
            return EXIT_EXISTING_FOUND
    else:
        r = run([
            "gh", "pr", "list",
            "--repo", repo,
            "--head", head,
            "--json", "number,url",
        ])
        if r.returncode != 0:
            fail("check-existing: GitHub API query failed. "
                 "Check gh auth status.")

        try:
            prs = json.loads(r.stdout) if r.stdout.strip() else []
        except json.JSONDecodeError:
            fail("check-existing: failed to parse GitHub API response")
            return EXIT_ARG_ERROR  # unreachable

        if prs:
            result = {"number": prs[0]["number"], "url": prs[0]["url"]}
            print(json.dumps(result, indent=2))
            return EXIT_EXISTING_FOUND

    # No existing PR found
    info(f"No existing PR/MR found for head={head} on {repo}")
    return EXIT_SUCCESS


def _check_existing_gitlab(repo: str, head: str) -> int:
    """GitLab check-existing: use glab mr list with source_project_id filtering."""
    source_branch = head
    source_project = ""

    if ":" in head:
        # project:branch format -- extract source project for cross-fork filtering
        source_project, source_branch = head.split(":", 1)

    r = run([
        "glab", "mr", "list",
        "--repo", repo,
        "--source-branch", source_branch,
        "--output", "json",
    ])
    if r.returncode != 0:
        fail("check-existing: GitLab API query failed. "
             "Check glab auth status.")

    try:
        mrs = json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError:
        fail("check-existing: failed to parse GitLab API response")
        return EXIT_ARG_ERROR  # unreachable

    if source_project:
        # Resolve the fork's numeric project ID to filter by source_project_id
        encoded = source_project.replace("/", "%2F")
        r = run(["glab", "api", f"projects/{encoded}", "--jq", ".id"])
        if r.returncode != 0 or not r.stdout.strip():
            fail(f"check-existing: could not resolve project ID "
                 f"for '{source_project}'")

        try:
            project_id = int(r.stdout.strip())
        except ValueError:
            fail(f"check-existing: invalid project ID from API: "
                 f"{r.stdout.strip()!r}")
            return EXIT_ARG_ERROR  # unreachable

        matching = [
            mr for mr in mrs
            if mr.get("source_project_id") == project_id
        ]
        if matching:
            print(json.dumps(matching[0], indent=2))
            return EXIT_EXISTING_FOUND
    else:
        if mrs:
            print(json.dumps(mrs[0], indent=2))
            return EXIT_EXISTING_FOUND

    info(f"No existing PR/MR found for head={head} on {repo}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: create-pr
# ---------------------------------------------------------------------------

def cmd_create_pr(args: argparse.Namespace) -> int:
    """Create a GitHub pull request via the gh CLI."""
    if not args.base:
        fail("Missing required argument: --base")
    if not args.head:
        fail("Missing required argument: --head")
    if not args.title:
        fail("Missing required argument: --title")

    cmd: list[str] = ["gh", "pr", "create"]

    if args.draft:
        cmd.append("--draft")

    if args.repo:
        cmd.extend(["--repo", args.repo])

    cmd.extend(["--base", args.base, "--head", args.head, "--title", args.title])

    if args.body_file:
        if not Path(args.body_file).is_file():
            fail(f"create-pr: body file not found: {args.body_file}")
        cmd.extend(["--body-file", args.body_file])
    elif args.body is not None:
        cmd.extend(["--body", args.body])
    else:
        cmd.extend(["--body", ""])

    if args.labels:
        cmd.extend(["--label", args.labels])

    info(f"Creating PR: {args.title}")
    result = run(cmd, capture=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        sys.exit(EXIT_CREATE_FAIL)

    pr_url = result.stdout.strip()
    if pr_url:
        print(pr_url)
    info(f"PR created: {pr_url}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: create-mr
# ---------------------------------------------------------------------------

def cmd_create_mr(args: argparse.Namespace) -> int:
    """Create a GitLab merge request via the glab CLI."""
    if not args.source:
        fail("Missing required argument: --source")
    if not args.target:
        fail("Missing required argument: --target")
    if not args.title:
        fail("Missing required argument: --title")

    cmd: list[str] = ["glab", "mr", "create", "--yes"]

    if args.draft:
        cmd.append("--draft")

    if args.project:
        cmd.extend(["--repo", args.project])

    if args.head:
        cmd.extend(["--head", args.head])

    cmd.extend([
        "--source-branch", args.source,
        "--target-branch", args.target,
        "--title", args.title,
    ])

    description = args.description or ""
    if args.desc_file:
        desc_path = Path(args.desc_file)
        if not desc_path.is_file():
            fail(f"create-mr: description file not found: {args.desc_file}")
        description = desc_path.read_text(encoding="utf-8")

    if description:
        cmd.extend(["--description", description])

    info(f"Creating MR: {args.title}")
    result = run(cmd, capture=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        sys.exit(EXIT_CREATE_FAIL)

    mr_url = result.stdout.strip()
    if mr_url:
        print(mr_url)
    info(f"MR created: {mr_url}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: save-metadata
# ---------------------------------------------------------------------------

def cmd_save_metadata(args: argparse.Namespace) -> int:
    """Write a JSON metadata file from key=value pairs."""
    file_path = args.file
    pairs: list[str] = args.pair or []

    if not file_path:
        fail("Missing required argument: --file")
    if not pairs:
        fail("save-metadata: no key=value pairs provided")

    data: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            fail(f"save-metadata: unexpected argument: {pair} "
                 f"(expected key=value)")
        key, _, value = pair.partition("=")
        # All values stored as JSON strings to avoid leading-zero truncation
        # (e.g., "007" -> 7) and to keep the output type-stable.
        data[key] = value

    # Sort keys for stable output (Python dicts preserve insertion order)
    sorted_data = dict(sorted(data.items()))

    # Create parent directory if needed
    out_path = Path(file_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with json.dumps -- proper encoding of all special characters
    out_path.write_text(
        json.dumps(sorted_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    info(f"Metadata saved to {file_path}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommand parsers."""
    parser = argparse.ArgumentParser(
        description="Deterministic publish operations for ai-workflows.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # -- preflight --
    p_preflight = subparsers.add_parser(
        "preflight",
        help="Pre-flight checks (auth, branch, uncommitted changes)",
    )
    p_preflight.add_argument(
        "--platform",
        choices=["github", "gitlab"],
        default="github",
        help="Which CLI to check (default: github)",
    )

    # -- push --
    p_push = subparsers.add_parser(
        "push",
        help="Push a branch to a remote",
    )
    p_push.add_argument("--remote", required=True, help="Git remote name")
    p_push.add_argument("--branch", required=True, help="Branch name to push")

    # -- check-existing --
    p_check = subparsers.add_parser(
        "check-existing",
        help="Check whether a PR/MR already exists for a branch",
    )
    p_check.add_argument("--repo", required=True, help="Target repository")
    p_check.add_argument("--head", required=True, help="Branch or owner:branch")
    p_check.add_argument(
        "--platform",
        choices=["github", "gitlab"],
        default="github",
        help="Which platform (default: github)",
    )

    # -- create-pr --
    p_pr = subparsers.add_parser(
        "create-pr",
        help="Create a GitHub pull request via gh CLI",
    )
    p_pr.add_argument("--repo", default="", help="Target repository")
    p_pr.add_argument("--base", required=True, help="Base branch")
    p_pr.add_argument("--head", required=True, help="Head ref")
    p_pr.add_argument("--title", required=True, help="PR title")
    p_pr.add_argument("--body-file", default="", help="Path to body file")
    p_pr.add_argument("--body", default=None, help="Inline PR body text")
    p_pr.add_argument(
        "--draft", action="store_true", default=True,
        help="Create as draft PR (default: true)",
    )
    p_pr.add_argument(
        "--no-draft", dest="draft", action="store_false",
        help="Create as non-draft PR",
    )
    p_pr.add_argument("--labels", default="", help="Comma-separated labels")

    # -- create-mr --
    p_mr = subparsers.add_parser(
        "create-mr",
        help="Create a GitLab merge request via glab CLI",
    )
    p_mr.add_argument("--project", default="", help="Upstream project path")
    p_mr.add_argument("--source", required=True, help="Source branch")
    p_mr.add_argument("--target", required=True, help="Target branch")
    p_mr.add_argument("--title", required=True, help="MR title")
    p_mr.add_argument("--description", default="", help="MR description text")
    p_mr.add_argument("--desc-file", default="", help="Path to description file")
    p_mr.add_argument(
        "--draft", action="store_true", default=True,
        help="Create as draft MR (default: true)",
    )
    p_mr.add_argument(
        "--no-draft", dest="draft", action="store_false",
        help="Create as non-draft MR",
    )
    p_mr.add_argument("--head", default="", help="Fork project path")

    # -- save-metadata --
    p_meta = subparsers.add_parser(
        "save-metadata",
        help="Write publish-metadata.json",
    )
    p_meta.add_argument("--file", required=True, help="Output file path")
    p_meta.add_argument(
        "pair", nargs="*", metavar="key=value",
        help="Key=value pairs (positional, repeatable)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUBCOMMAND_MAP = {
    "preflight": cmd_preflight,
    "push": cmd_push,
    "check-existing": cmd_check_existing,
    "create-pr": cmd_create_pr,
    "create-mr": cmd_create_mr,
    "save-metadata": cmd_save_metadata,
}


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return EXIT_ARG_ERROR

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if handler is None:
        fail(f"Unknown subcommand: {args.subcommand}. "
             f"Run with --help for usage.")

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
