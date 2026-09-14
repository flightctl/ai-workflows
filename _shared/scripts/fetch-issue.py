#!/usr/bin/env python3
"""Jira issue fetching for ai-workflows.

Provides reusable subcommands for fetching Jira issue data via the
REST API.  Each subcommand handles one discrete, deterministic
operation -- the calling skill file retains ownership of AI-dependent
work (issue analysis, triage decisions, summarisation).

Subcommands:
  get     Fetch a single Jira issue by key
  search  Search for issues via JQL

Environment variables:
  JIRA_URL    (required) Jira base URL (e.g. https://issues.redhat.com)
  JIRA_TOKEN  (required) Personal access token for Bearer auth
  JIRA_EMAIL  (optional) When set, use Basic auth (email:token) for
              Atlassian Cloud instances instead of Bearer auth

Usage:
  fetch-issue.py get <KEY> [--fields f1,f2,...] [--comments]
                 [--comment-limit N] [--links] [--link-fields f1,f2,...]
                 [--parent] [--parent-fields f1,f2,...]
  fetch-issue.py search <JQL> [--fields f1,f2,...] [--max-results N]

Exit codes:
  0 -- success
  1 -- runtime error (missing env var, HTTP failure, issue not found)
  2 -- invalid arguments (from argparse)
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from typing import Any, NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1
# argparse uses exit code 2 for usage errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _get_env(name: str) -> str:
    """Return a required environment variable or fail."""
    import os
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def _build_auth_header() -> str:
    """Build the Authorization header value from environment variables.

    When JIRA_EMAIL is set, uses Basic auth (email:token) for Atlassian
    Cloud instances.  Otherwise uses Bearer auth with the token alone.
    """
    import os
    token = _get_env("JIRA_TOKEN")
    email = os.environ.get("JIRA_EMAIL", "").strip()

    if email:
        credentials = f"{email}:{token}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    return f"Bearer {token}"


def _jira_request(url: str, auth_header: str) -> Any:
    """Perform a GET request to the Jira REST API and return parsed JSON.

    Args:
        url: Full URL to request.
        auth_header: Value for the Authorization header.

    Returns:
        Parsed JSON response.

    Raises:
        SystemExit: On HTTP errors or JSON parse failures.
    """
    req = urllib.request.Request(url)
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            pass
        if exc.code == 404:
            fail(f"Issue not found (HTTP 404): {url}")
        fail(f"HTTP {exc.code}: {body}")
    except urllib.error.URLError as exc:
        fail(f"Request failed: {exc.reason}")

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        fail(f"Failed to parse JSON response from {url}")


# ---------------------------------------------------------------------------
# Subcommand: get
# ---------------------------------------------------------------------------

DEFAULT_FIELDS = "summary,description,issuetype,status,priority,labels"
DEFAULT_LINK_FIELDS = "summary,status"
DEFAULT_PARENT_FIELDS = "summary,status,issuetype"


def cmd_get(args: argparse.Namespace) -> int:
    """Fetch a single Jira issue by key.

    Prints a JSON object to stdout with the issue key, requested fields,
    and optionally comments, links, and parent data.
    """
    key = args.key
    fields = args.fields
    include_comments = args.comments
    comment_limit = args.comment_limit
    include_links = args.links
    link_fields = args.link_fields
    include_parent = args.parent
    parent_fields = args.parent_fields

    jira_url = _get_env("JIRA_URL").rstrip("/")
    auth_header = _build_auth_header()

    # Build the fields list for the API request
    api_fields = fields
    if include_links and "issuelinks" not in api_fields:
        api_fields = f"{api_fields},issuelinks"
    if include_parent and "parent" not in api_fields:
        api_fields = f"{api_fields},parent"
    if include_comments and "comment" not in api_fields:
        api_fields = f"{api_fields},comment"

    url = f"{jira_url}/rest/api/2/issue/{key}?fields={api_fields}"
    info(f"Fetching issue {key}")

    data = _jira_request(url, auth_header)

    # Build output
    result: dict[str, Any] = {
        "key": data.get("key", key),
        "fields": {},
    }

    raw_fields = data.get("fields", {})

    # Extract requested fields (exclude internal fields we added)
    requested = [f.strip() for f in fields.split(",")]
    for field_name in requested:
        if field_name in raw_fields:
            result["fields"][field_name] = raw_fields[field_name]

    # Comments
    if include_comments:
        comment_data = raw_fields.get("comment", {})
        all_comments = comment_data.get("comments", [])

        if comment_limit > 0:
            all_comments = all_comments[:comment_limit]

        result["comments"] = [
            {
                "id": c.get("id"),
                "author": (c.get("author") or {}).get("displayName", ""),
                "body": c.get("body", ""),
                "created": c.get("created", ""),
            }
            for c in all_comments
        ]

    # Links
    if include_links:
        issue_links = raw_fields.get("issuelinks", [])
        links_out: list[dict[str, Any]] = []
        link_field_list = [f.strip() for f in link_fields.split(",")]

        for link in issue_links:
            link_entry: dict[str, Any] = {
                "type": (link.get("type") or {}).get("name", ""),
            }

            # A link has either inwardIssue or outwardIssue
            linked_issue = link.get("outwardIssue") or link.get("inwardIssue")
            if linked_issue:
                link_entry["key"] = linked_issue.get("key", "")
                link_entry["direction"] = (
                    "outward" if "outwardIssue" in link else "inward"
                )
                linked_fields = linked_issue.get("fields", {})
                link_entry["fields"] = {
                    f: linked_fields.get(f)
                    for f in link_field_list
                    if f in linked_fields
                }
            links_out.append(link_entry)

        result["links"] = links_out

    # Parent
    if include_parent:
        parent_data = raw_fields.get("parent")
        if parent_data:
            parent_field_list = [f.strip() for f in parent_fields.split(",")]
            parent_raw = parent_data.get("fields", {})
            result["parent"] = {
                "key": parent_data.get("key", ""),
                "fields": {
                    f: parent_raw.get(f)
                    for f in parent_field_list
                    if f in parent_raw
                },
            }
        else:
            result["parent"] = None

    print(json.dumps(result, indent=2))
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: search
# ---------------------------------------------------------------------------

def cmd_search(args: argparse.Namespace) -> int:
    """Search for Jira issues via JQL.

    Prints a JSON object to stdout with the total count and matching
    issues, each with their key and requested fields.
    """
    jql = args.jql
    fields = args.fields
    max_results = args.max_results

    jira_url = _get_env("JIRA_URL").rstrip("/")
    auth_header = _build_auth_header()

    # URL-encode query parameters
    from urllib.parse import quote
    encoded_jql = quote(jql, safe="")
    encoded_fields = quote(fields, safe=",")

    url = (
        f"{jira_url}/rest/api/2/search"
        f"?jql={encoded_jql}"
        f"&fields={encoded_fields}"
        f"&maxResults={max_results}"
    )
    info(f"Searching: {jql}")

    data = _jira_request(url, auth_header)

    # Build output
    field_list = [f.strip() for f in fields.split(",")]
    issues: list[dict[str, Any]] = []

    for issue in data.get("issues", []):
        raw = issue.get("fields", {})
        issues.append({
            "key": issue.get("key", ""),
            "fields": {
                f: raw.get(f)
                for f in field_list
                if f in raw
            },
        })

    result = {
        "total": data.get("total", len(issues)),
        "issues": issues,
    }

    print(json.dumps(result, indent=2))
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with subcommand parsers."""
    parser = argparse.ArgumentParser(
        description="Jira issue fetching for ai-workflows.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # -- get --
    p_get = subparsers.add_parser(
        "get",
        help="Fetch a single Jira issue by key",
    )
    p_get.add_argument("key", help="Jira issue key (e.g. EDM-123)")
    p_get.add_argument(
        "--fields",
        default=DEFAULT_FIELDS,
        help=f"Comma-separated field names (default: {DEFAULT_FIELDS})",
    )
    p_get.add_argument(
        "--comments",
        action="store_true",
        help="Include comments in output",
    )
    p_get.add_argument(
        "--comment-limit",
        type=int,
        default=0,
        help="Max comments to return (default: 0 = all)",
    )
    p_get.add_argument(
        "--links",
        action="store_true",
        help="Include linked issues (one level deep)",
    )
    p_get.add_argument(
        "--link-fields",
        default=DEFAULT_LINK_FIELDS,
        help=f"Fields for linked issues (default: {DEFAULT_LINK_FIELDS})",
    )
    p_get.add_argument(
        "--parent",
        action="store_true",
        help="Include parent issue data",
    )
    p_get.add_argument(
        "--parent-fields",
        default=DEFAULT_PARENT_FIELDS,
        help=f"Fields for parent issue (default: {DEFAULT_PARENT_FIELDS})",
    )

    # -- search --
    p_search = subparsers.add_parser(
        "search",
        help="Search for issues via JQL",
    )
    p_search.add_argument("jql", help="JQL query string")
    p_search.add_argument(
        "--fields",
        default=DEFAULT_FIELDS,
        help=f"Comma-separated field names (default: {DEFAULT_FIELDS})",
    )
    p_search.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Max results to return (default: 50)",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SUBCOMMAND_MAP = {
    "get": cmd_get,
    "search": cmd_search,
}


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return EXIT_ERROR

    handler = SUBCOMMAND_MAP.get(args.subcommand)
    if handler is None:
        fail(f"Unknown subcommand: {args.subcommand}. "
             f"Run with --help for usage.")

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
