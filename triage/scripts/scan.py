#!/usr/bin/env python3
"""Scan Jira for unresolved and recently resolved bugs.

Fetches all unresolved bugs and recently resolved bugs from a Jira
project using JQL with key-based cursor pagination, normalizes the
data, and writes issues.json and resolved.json.

Usage: scan.py PROJECT_KEY [--window-days 90] [--output-dir DIR]

Environment:
    JIRA_URL    Jira instance base URL (e.g., https://redhat.atlassian.net)
    JIRA_TOKEN  API token or Personal Access Token
    JIRA_EMAIL  (optional) account email — when set, uses Basic auth
                (required for API tokens); when absent, uses Bearer auth

Exit codes:
    0 — scan completed successfully
    1 — missing input or configuration error
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

PAGE_SIZE = 50
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

UNRESOLVED_FIELDS = (
    "summary,status,priority,assignee,reporter,"
    "created,updated,labels,components,description"
)
RESOLVED_FIELDS = f"{UNRESOLVED_FIELDS},resolution,resolutiondate"

_ADF_BLOCK_CONTAINERS = frozenset({
    "doc", "bulletList", "orderedList", "listItem",
    "blockquote", "table", "tableRow", "tableCell", "tableHeader",
    "panel", "taskList", "decisionList",
    "expand", "nestedExpand", "layoutSection", "layoutColumn",
})

SearchFn = Callable[[str, str, int], dict[str, Any]]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScanError(Exception):
    """Base exception for scan errors."""


class JiraAPIError(ScanError):
    """Jira API returned an error after exhausting retries."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Jira API {status_code}: {body[:500]}")


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        return ""


def _retry_delay(headers: Any, attempt: int) -> float:
    retry_after = headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(1, int(retry_after))
        except (ValueError, TypeError):
            pass
    return RETRY_BACKOFF_BASE ** attempt


def _http_get(url: str, headers: dict[str, str]) -> bytes:
    """HTTP GET with retry on transient failures (429, 5xx)."""
    ctx = ssl.create_default_context()

    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = _read_error_body(exc)
            if exc.code == 429 and attempt < MAX_RETRIES:
                time.sleep(_retry_delay(exc.headers, attempt))
                continue
            if exc.code >= 500 and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_BASE ** attempt)
                continue
            raise JiraAPIError(exc.code, body) from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_BASE ** attempt)
                continue
            raise ScanError(f"Cannot reach Jira: {exc.reason}") from exc

    # defensive: every loop iteration returns or raises, but this
    # satisfies the type checker and guards against future refactors
    raise ScanError(f"Retries exhausted after {MAX_RETRIES + 1} attempts")


def build_auth_header(token: str, email: str | None = None) -> str:
    """Build the Authorization header value.

    API tokens (JIRA_EMAIL set) use Basic auth; PATs use Bearer.
    """
    if email:
        credentials = base64.b64encode(
            f"{email}:{token}".encode("utf-8"),
        ).decode("ascii")
        return f"Basic {credentials}"
    return f"Bearer {token}"


def jira_search(
    base_url: str,
    auth_header: str,
    jql: str,
    fields: str,
    max_results: int = PAGE_SIZE,
) -> dict[str, Any]:
    """Execute a single JQL search against the Jira REST API."""
    params = urllib.parse.urlencode({
        "jql": jql,
        "fields": fields,
        "maxResults": max_results,
    })
    url = f"{base_url.rstrip('/')}/rest/api/3/search/jql?{params}"
    headers = {
        "Authorization": auth_header,
        "Accept": "application/json",
    }
    raw = _http_get(url, headers)
    return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def fetch_all_issues(
    search_fn: SearchFn,
    jql_base: str,
    fields: str,
) -> list[dict[str, Any]]:
    """Fetch all issues matching a JQL filter using key-based cursor pagination.

    ``search_fn(jql, fields, max_results)`` is called repeatedly with
    ``AND key > '{last_key}' ORDER BY key ASC`` appended to the base JQL
    until a page returns fewer than PAGE_SIZE results.
    """
    all_issues: list[dict[str, Any]] = []
    last_key = ""

    while True:
        jql = jql_base
        if last_key:
            jql += f" AND key > '{last_key}'"
        jql += " ORDER BY key ASC"

        data = search_fn(jql, fields, PAGE_SIZE)
        page = data.get("issues", [])
        if not page:
            break

        all_issues.extend(page)
        last_key = page[-1]["key"]

        if len(page) < PAGE_SIZE:
            break

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for issue in all_issues:
        key = issue["key"]
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    return deduped


# ---------------------------------------------------------------------------
# ADF text extraction
# ---------------------------------------------------------------------------

def extract_text(value: Any) -> str:
    """Extract plain text from a value that may be a string or ADF JSON.

    Handles Jira's Atlassian Document Format by recursively walking
    content nodes and concatenating text leaves, with newlines between
    block-level elements.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "text":
            return value.get("text", "")
        parts = [extract_text(c) for c in value.get("content", [])]
        if node_type in _ADF_BLOCK_CONTAINERS:
            return "\n".join(p for p in parts if p)
        return "".join(parts)
    if isinstance(value, list):
        return "\n".join(p for p in (extract_text(item) for item in value) if p)
    return ""


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _name_or_default(field: Any, key: str = "name", default: str = "") -> str:
    """Extract a named attribute from a Jira object field, or return default."""
    if isinstance(field, dict):
        return field.get(key, default)
    return default


def normalize_issue(
    raw: dict[str, Any],
    *,
    include_resolution: bool = False,
) -> dict[str, Any]:
    """Normalize a raw Jira API issue into a flat dictionary."""
    fields = raw.get("fields", {})

    normalized: dict[str, Any] = {
        "key": raw.get("key", ""),
        "summary": fields.get("summary", ""),
        "status": _name_or_default(fields.get("status")),
        "priority": _name_or_default(fields.get("priority")),
        "assignee": _name_or_default(
            fields.get("assignee"), "displayName", "Unassigned",
        ),
        "reporter": _name_or_default(fields.get("reporter"), "displayName"),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "labels": fields.get("labels", []),
        "components": [
            _name_or_default(c)
            for c in fields.get("components", [])
            if isinstance(c, dict)
        ],
        "description": extract_text(fields.get("description")),
    }

    if include_resolution:
        normalized["resolution"] = _name_or_default(fields.get("resolution"))
        normalized["resolved"] = fields.get("resolutiondate", "")

    return normalized


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def build_summary(issues: list[dict[str, Any]]) -> str:
    """Build a human-readable summary grouped by priority and status."""
    priority_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for issue in issues:
        priority_counts[issue.get("priority") or "Unknown"] += 1
        status_counts[issue.get("status") or "Unknown"] += 1

    lines: list[str] = []
    if priority_counts:
        lines.append("By priority:")
        for name, count in priority_counts.most_common():
            lines.append(f"  {name}: {count}")
    if status_counts:
        lines.append("By status:")
        for name, count in status_counts.most_common():
            lines.append(f"  {name}: {count}")
    return "\n".join(lines)


def build_output(
    project: str,
    jira_url: str,
    issues: list[dict[str, Any]],
    scanned_at: str,
    *,
    window_days: int | None = None,
) -> dict[str, Any]:
    """Assemble the output JSON structure (pure — no I/O or clock)."""
    data: dict[str, Any] = {
        "project": project,
        "jiraBaseUrl": jira_url.rstrip("/"),
        "scannedAt": scanned_at,
        "totalCount": len(issues),
        "issues": issues,
    }
    if window_days is not None:
        data["windowDays"] = window_days
    return data


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON object to a file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Jira for unresolved and recently resolved bugs.",
    )
    parser.add_argument(
        "project",
        help="Jira project key (e.g., EDM)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=90,
        help="Number of days to look back for resolved bugs (default: 90)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: .artifacts/triage/{PROJECT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = args.project
    window_days = args.window_days
    output_dir = args.output_dir or Path(f".artifacts/triage/{project}")

    jira_url = os.environ.get("JIRA_URL", "").strip()
    jira_token = os.environ.get("JIRA_TOKEN", "").strip()
    jira_email = os.environ.get("JIRA_EMAIL", "").strip() or None
    if not jira_url:
        print("Error: JIRA_URL environment variable is not set", file=sys.stderr)
        return 1
    if not jira_token:
        print("Error: JIRA_TOKEN environment variable is not set", file=sys.stderr)
        return 1

    auth_header = build_auth_header(jira_token, jira_email)
    search = partial(jira_search, jira_url, auth_header)

    try:
        unresolved_jql = (
            f"project = {project} AND issuetype = Bug "
            f"AND resolution = Unresolved"
        )
        raw_unresolved = fetch_all_issues(
            search, unresolved_jql, UNRESOLVED_FIELDS,
        )
        unresolved = [normalize_issue(r) for r in raw_unresolved]

        resolved_jql = (
            f"project = {project} AND issuetype = Bug "
            f"AND resolution != Unresolved "
            f"AND resolved >= -{window_days}d"
        )
        raw_resolved = fetch_all_issues(
            search, resolved_jql, RESOLVED_FIELDS,
        )
        resolved = [
            normalize_issue(r, include_resolution=True) for r in raw_resolved
        ]
    except ScanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    issues_path = output_dir / "issues.json"
    resolved_path = output_dir / "resolved.json"

    write_json_file(
        issues_path,
        build_output(project, jira_url, unresolved, scanned_at),
    )
    write_json_file(
        resolved_path,
        build_output(
            project, jira_url, resolved, scanned_at,
            window_days=window_days,
        ),
    )

    print(f"Scan complete: {len(unresolved)} unresolved bugs in {project}")
    print(f"Resolved (last {window_days} days): {len(resolved)} bugs")
    print()

    if unresolved:
        print(build_summary(unresolved))
        print()

    print("Data saved to:")
    print(f"  {issues_path}")
    print(f"  {resolved_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
