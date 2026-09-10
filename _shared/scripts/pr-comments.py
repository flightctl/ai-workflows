#!/usr/bin/env python3
"""PR comment operations for ai-workflows.

Provides reusable subcommands for fetching, replying to, and tracking
PR comments during respond/feedback workflow phases.  Each subcommand
handles one discrete, deterministic operation -- the calling skill file
retains ownership of AI-dependent work (response generation, comment
prioritisation, user confirmation prompts).

Subcommands:
  fetch   Fetch PR comments from GitHub, filter, and output unified JSON
  reply   Post a reply to a PR comment (inline or top-level)
  log     Record a comment as addressed in a responses log file

Usage:
  pr-comments.py fetch --owner OWNER --repo REPO --pr NUMBER
                 [--since TIMESTAMP] [--responses-log FILE]
                 [--include-review-threads]
  pr-comments.py reply --owner OWNER --repo REPO --pr NUMBER
                 --body-file FILE [--comment-id ID]
  pr-comments.py log --responses-log FILE --comment-id ID
                 [--response-summary TEXT]

Exit codes:
  0 -- success
  1 -- runtime error (gh CLI failure, I/O error)
  2 -- usage/argument error (from argparse)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
# argparse uses exit code 2 for usage errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_RUNTIME_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _run(
    cmd: list[str],
    *,
    capture: bool = True,
    check: bool = False,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with text mode and optional output capture.

    Args:
        cmd: Command and arguments to execute.
        capture: If True, capture stdout and stderr (default: True).
        check: If True, raise CalledProcessError on non-zero exit.
        timeout: Maximum seconds to wait before killing the process
            (default: 120).

    Returns:
        The completed process with text-mode stdout/stderr.  On timeout,
        returns a synthetic failure result (returncode -1) with the
        timeout message in stderr.
    """
    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            cmd,
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {' '.join(cmd)}",
        )


def _emit_json(data: Any) -> None:
    """Write a JSON value to stdout with consistent formatting."""
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: fetch
# ---------------------------------------------------------------------------

def cmd_fetch(args: argparse.Namespace) -> int:
    """Fetch PR comments from GitHub, filter, and output unified JSON.

    Fetches three types of comments via the ``gh`` CLI:
      1. Line-level review comments (REST API, paginated)
      2. Top-level comments and reviews (``gh pr view --json``)
      3. Review thread resolution status (GraphQL, optional)

    Applies ``--since`` and ``--responses-log`` filters, then prints a
    unified JSON array to stdout.
    """
    owner = args.owner
    repo = args.repo
    pr = args.pr
    since = args.since
    responses_log = args.responses_log
    include_review_threads = args.include_review_threads

    # Load already-addressed comment IDs from responses log
    addressed_ids: set[str] = set()
    if responses_log:
        log_path = Path(responses_log)
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            for line_num, raw_line in enumerate(lines, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    fail(
                        f"fetch: malformed JSON on line {line_num} "
                        f"of {responses_log}",
                    )
                if "comment_id" in entry:
                    addressed_ids.add(str(entry["comment_id"]))

    comments: list[dict[str, Any]] = []

    # 1. Line-level review comments
    r = _run([
        "gh", "api",
        f"repos/{owner}/{repo}/pulls/{pr}/comments",
        "--paginate",
        "--slurp",
    ])
    if r.returncode != 0:
        fail(f"fetch: failed to fetch review comments: {r.stderr.strip()}")

    try:
        raw = json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError:
        fail("fetch: failed to parse review comments JSON")

    # --slurp wraps each page in an array; flatten to a single list
    review_comments: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, list):
            review_comments.extend(item)
        else:
            review_comments.append(item)

    for rc in review_comments:
        comment: dict[str, Any] = {
            "type": "line_comment",
            "id": rc.get("id"),
            "author": rc.get("user", {}).get("login", ""),
            "body": rc.get("body", ""),
            "created_at": rc.get("created_at", ""),
            "path": rc.get("path", ""),
            "line": rc.get("line") or rc.get("original_line"),
            "in_reply_to_id": rc.get("in_reply_to_id"),
            "url": rc.get("html_url", ""),
        }
        comments.append(comment)

    # 2. Top-level comments + reviews
    r = _run([
        "gh", "pr", "view", str(pr),
        "--repo", f"{owner}/{repo}",
        "--json", "comments,reviews,url",
    ])
    if r.returncode != 0:
        fail(f"fetch: failed to fetch PR data: {r.stderr.strip()}")

    try:
        pr_data = json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        fail("fetch: failed to parse PR data JSON")

    pr_url = pr_data.get("url", "")

    for tc in pr_data.get("comments", []):
        comment = {
            "type": "top_level",
            "id": tc.get("id"),
            "author": tc.get("author", {}).get("login", ""),
            "body": tc.get("body", ""),
            "created_at": tc.get("createdAt", ""),
            "url": tc.get("url") or pr_url,
        }
        comments.append(comment)

    for rv in pr_data.get("reviews", []):
        comment = {
            "type": "review",
            "id": rv.get("id"),
            "author": rv.get("author", {}).get("login", ""),
            "body": rv.get("body", ""),
            "created_at": rv.get("submittedAt", ""),
            "url": pr_url,
        }
        comments.append(comment)

    # 3. Review thread resolution status (optional)
    if include_review_threads:
        query = (
            "query($owner: String!, $repo: String!, $pr: Int!) {"
            "  repository(owner: $owner, name: $repo) {"
            "    pullRequest(number: $pr) {"
            "      reviewThreads(first: 100) {"
            "        nodes {"
            "          isResolved"
            "          comments(first: 1) {"
            "            nodes { id databaseId }"
            "          }"
            "        }"
            "      }"
            "    }"
            "  }"
            "}"
        )
        r = _run([
            "gh", "api", "graphql",
            "-F", f"owner={owner}",
            "-F", f"repo={repo}",
            "-F", f"pr={pr}",
            "-f", f"query={query}",
        ])
        if r.returncode == 0 and r.stdout.strip():
            try:
                gql_data = json.loads(r.stdout)
                threads = (
                    gql_data.get("data", {})
                    .get("repository", {})
                    .get("pullRequest", {})
                    .get("reviewThreads", {})
                    .get("nodes", [])
                )
                # Build a map: databaseId -> isResolved
                resolved_map: dict[int, bool] = {}
                for thread in threads:
                    is_resolved = thread.get("isResolved", False)
                    thread_comments = (
                        thread.get("comments", {}).get("nodes", [])
                    )
                    if thread_comments:
                        db_id = thread_comments[0].get("databaseId")
                        if db_id is not None:
                            resolved_map[db_id] = is_resolved

                # Annotate line_comment entries with is_resolved
                for c in comments:
                    if (c["type"] == "line_comment"
                            and c["id"] in resolved_map):
                        c["is_resolved"] = resolved_map[c["id"]]
            except (json.JSONDecodeError, KeyError, TypeError):
                info("fetch: could not parse review thread data; "
                     "skipping resolution status")

    # Apply filters
    filtered: list[dict[str, Any]] = []
    for c in comments:
        # Filter by --since
        if since and c.get("created_at"):
            if c["created_at"] < since:
                continue

        # Filter by responses log
        if addressed_ids and str(c.get("id", "")) in addressed_ids:
            continue

        filtered.append(c)

    _emit_json(filtered)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: reply
# ---------------------------------------------------------------------------

def cmd_reply(args: argparse.Namespace) -> int:
    """Post a reply to a PR comment (inline or top-level).

    When ``--comment-id`` is given, posts an inline reply to that review
    comment via the REST API.  Otherwise posts a top-level PR comment
    using ``gh pr comment``.

    Prints JSON with ``comment_id`` and ``url`` on success.
    """
    owner = args.owner
    repo = args.repo
    pr = args.pr
    body_file = args.body_file
    comment_id = args.comment_id

    if not Path(body_file).is_file():
        fail(f"reply: body file not found: {body_file}")

    if comment_id:
        # Inline reply to a review comment
        r = _run([
            "gh", "api",
            f"repos/{owner}/{repo}/pulls/{pr}/comments"
            f"/{comment_id}/replies",
            "--field", f"body=@{body_file}",
        ])
    else:
        # Top-level PR comment
        r = _run([
            "gh", "pr", "comment", str(pr),
            "--repo", f"{owner}/{repo}",
            "--body-file", body_file,
        ])

    if r.returncode != 0:
        fail(f"reply: failed to post comment: {r.stderr.strip()}")

    # Build output
    result: dict[str, Any] = {}
    if comment_id and r.stdout.strip():
        try:
            response = json.loads(r.stdout)
            result["comment_id"] = response.get("id")
            result["url"] = response.get("html_url", "")
        except json.JSONDecodeError:
            result["comment_id"] = None
            result["url"] = ""
    elif not comment_id and r.stdout.strip():
        result["comment_id"] = None
        result["url"] = r.stdout.strip()
    else:
        result["comment_id"] = None
        result["url"] = ""

    _emit_json(result)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: log
# ---------------------------------------------------------------------------

def cmd_log(args: argparse.Namespace) -> int:
    """Record a comment as addressed in the responses log.

    Appends a JSON line to ``--responses-log`` with the comment ID,
    current UTC timestamp, and optional summary.  Creates the file
    (and parent directories) if it does not exist.
    """
    responses_log = args.responses_log
    comment_id = args.comment_id
    summary = args.response_summary or ""

    log_path = Path(responses_log)

    # Create parent directory if needed
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "comment_id": comment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    info(f"Logged comment {comment_id} to {responses_log}")
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommand parsers."""
    parser = argparse.ArgumentParser(
        description="PR comment operations for ai-workflows.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # -- fetch --
    p_fetch = subparsers.add_parser(
        "fetch",
        help="Fetch PR comments from GitHub, filter, and output JSON",
    )
    p_fetch.add_argument("--owner", required=True, help="Repository owner")
    p_fetch.add_argument("--repo", required=True, help="Repository name")
    p_fetch.add_argument("--pr", required=True, type=int, help="PR number")
    p_fetch.add_argument(
        "--since", default="",
        help="ISO 8601 timestamp cutoff (exclude older comments)",
    )
    p_fetch.add_argument(
        "--responses-log", default="",
        help="Path to responses log (exclude addressed comment IDs)",
    )
    p_fetch.add_argument(
        "--include-review-threads", action="store_true",
        help="Use GraphQL to include review thread resolution status",
    )

    # -- reply --
    p_reply = subparsers.add_parser(
        "reply",
        help="Post a reply to a PR comment",
    )
    p_reply.add_argument("--owner", required=True, help="Repository owner")
    p_reply.add_argument("--repo", required=True, help="Repository name")
    p_reply.add_argument("--pr", required=True, type=int, help="PR number")
    p_reply.add_argument(
        "--body-file", required=True,
        help="Path to file containing comment body",
    )
    p_reply.add_argument(
        "--comment-id", default="",
        help="Review comment ID for inline reply (omit for top-level)",
    )

    # -- log --
    p_log = subparsers.add_parser(
        "log",
        help="Record a comment as addressed in a responses log",
    )
    p_log.add_argument(
        "--responses-log", required=True,
        help="Path to the responses log file",
    )
    p_log.add_argument(
        "--comment-id", required=True,
        help="Comment ID to record",
    )
    p_log.add_argument(
        "--response-summary", default="",
        help="Summary of the response",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUBCOMMAND_MAP = {
    "fetch": cmd_fetch,
    "reply": cmd_reply,
    "log": cmd_log,
}


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return EXIT_RUNTIME_ERROR

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if handler is None:
        fail(f"Unknown subcommand: {args.subcommand}. "
             f"Run with --help for usage.")

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
