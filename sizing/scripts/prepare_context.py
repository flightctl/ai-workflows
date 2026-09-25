#!/usr/bin/env python3
"""Fetch and compact Jira Features for the sizing workflow.

Use the configured Jira CLI when available; on failure, use the shared
fetch-issue.py REST helper if its credentials are configured. Capture raw JSON
in Python, keep only sizing-relevant fields, and write the compact analysis
packet to stdout for the AI phase. For a valid command, main() returns 0 when it
writes a packet (even if it warns that results may be truncated) and 1 for
fetch or validation errors; argparse usage errors exit 2. Diagnostics go to
stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, estimate_tokens, slug, text_value


FIELDS = "summary,description,issuetype,status,priority,fixVersions,customfield_10795"
MAX_COMMENTS = 3
MAX_COMMENT_CHARS = 700
JIRA_SUBPROCESS_TIMEOUT_SECONDS = 120
BOT_AUTHOR_RE = re.compile(r"\b(bot|automation|automated)\b", re.IGNORECASE)
SIZING_COMMENT_RE = re.compile(r"^\s*(?:h\d\.\s*)?Sizing Assessment\b", re.IGNORECASE)
STATUS_LABEL = r"[\w/-]+(?:\s+[\w/-]+){0,4}"
STATUS_COMMENT_RE = re.compile(
    rf"\s*(?:status\s+(?:was\s+)?changed(?:\s+from\s+{STATUS_LABEL}\s+to\s+{STATUS_LABEL}|"
    rf"\s+to\s+{STATUS_LABEL})?|(?:transitioned|moved)\s+from\s+{STATUS_LABEL}\s+to\s+{STATUS_LABEL})"
    rf"\s*[.!]?\s*",
    re.IGNORECASE,
)
ISSUE_KEY_RE = re.compile(r"[A-Z][A-Z0-9_]+-[0-9]+", re.ASCII | re.IGNORECASE)


def _fetch_script(path: str | None) -> Path:
    script = Path(path).expanduser() if path else REPO_ROOT / "_shared" / "scripts" / "fetch-issue.py"
    script = script.resolve()
    if not script.is_file():
        raise ValueError(f"shared Jira fetch script not found: {script}")
    return script


def _run_fetch(script: Path, *arguments: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(script), *arguments],
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=JIRA_SUBPROCESS_TIMEOUT_SECONDS,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(detail or f"Jira fetch failed with exit code {completed.returncode}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Jira fetch returned invalid JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("Jira fetch returned an unexpected response")
    return result


def _run_jira_cli(*arguments: str) -> Any:
    completed = subprocess.run(
        ["jira", *arguments],
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=JIRA_SUBPROCESS_TIMEOUT_SECONDS,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(detail or f"Jira CLI failed with exit code {completed.returncode}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Jira CLI returned invalid JSON: {exc}") from exc


def _flatten_adf(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    if node_type == "mention":
        return (node.get("attrs") or {}).get("text", "")
    if node_type == "emoji":
        return (node.get("attrs") or {}).get("shortName", "")
    parts = [_flatten_adf(child) for child in node.get("content", [])]
    block_types = {
        "doc", "bulletList", "orderedList", "blockquote", "table", "tableRow",
        "tableCell", "tableHeader", "listItem", "panel", "mediaSingle",
    }
    return ("\n" if node_type in block_types else "").join(parts)


def _normalize_cli_issue(issue: Any) -> dict[str, Any]:
    raw_issue = issue if isinstance(issue, dict) else {}
    fields = raw_issue.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("Jira CLI returned an issue without fields")

    normalized_fields = {
        "summary": fields.get("summary"),
        "description": _flatten_adf(fields.get("description")),
        "issuetype": fields.get("issuetype") or fields.get("issueType"),
        "status": fields.get("status"),
        "priority": fields.get("priority"),
        "fixVersions": fields.get("fixVersions", []),
        "customfield_10795": fields.get("customfield_10795"),
    }

    comment_data = fields.get("comment")
    raw_comments = comment_data.get("comments", []) if isinstance(comment_data, dict) else []
    comments = []
    for comment in raw_comments:
        if not isinstance(comment, dict):
            continue
        author = comment.get("author")
        comments.append({
            "author": author.get("displayName", "") if isinstance(author, dict) else "",
            "body": _flatten_adf(comment.get("body", "")),
            "created": comment.get("created", ""),
        })

    raw_links = fields.get("issuelinks") or fields.get("issueLinks") or []
    links = []
    if isinstance(raw_links, list):
        for link in raw_links:
            if not isinstance(link, dict):
                continue
            outward = link.get("outwardIssue")
            linked_issue = outward or link.get("inwardIssue")
            if not isinstance(linked_issue, dict):
                continue
            linked_fields = linked_issue.get("fields")
            if not isinstance(linked_fields, dict):
                linked_fields = {}
            link_type = link.get("type")
            links.append({
                "key": linked_issue.get("key", ""),
                "type": link_type.get("name", "") if isinstance(link_type, dict) else "",
                "direction": "outward" if outward else "inward",
                "fields": {
                    "summary": linked_fields.get("summary"),
                    "status": linked_fields.get("status"),
                },
            })

    return {
        "key": raw_issue.get("key", ""),
        "fields": normalized_fields,
        "comments": comments,
        "links": links,
    }


def _get_issue_cli(key: str) -> tuple[dict[str, Any], int]:
    raw_issue = _run_jira_cli("issue", "view", key, "--comments", "100", "--raw")
    issue = _normalize_cli_issue(raw_issue)
    raw_bytes = len(json.dumps(raw_issue, ensure_ascii=False, indent=2).encode("utf-8"))
    return issue, raw_bytes


def _single_cli(key: str) -> tuple[dict[str, Any], int]:
    fetched, raw_bytes = _get_issue_cli(key)
    feature = _feature(fetched)
    if not feature["key"]:
        feature["key"] = key
    return {
        "mode": "single",
        "context": feature["key"],
        "features": [feature],
    }, raw_bytes


def _release_cli(
    project: str,
    version: str,
    max_results: int,
) -> tuple[dict[str, Any], int]:
    jql = (
        f"project = {_jql_literal(project)} AND "
        f"fixVersion = {_jql_literal(version)} AND issuetype = Feature"
    )
    keys: list[str] = []
    seen: set[str] = set()
    raw_bytes = 0
    start_at = 0
    while len(keys) < max_results:
        page_size = min(100, max_results - len(keys))
        page = _run_jira_cli(
            "issue", "list", "--project", project, "--jql", jql, "--raw",
            "--paginate", f"{start_at}:{page_size}",
        )
        raw_bytes += len(json.dumps(page, ensure_ascii=False, indent=2).encode("utf-8"))
        if not isinstance(page, list):
            raise ValueError("Jira CLI search returned an unexpected response")
        previous_count = len(keys)
        page_keys = [
            text_value(item.get("key"))
            for item in page
            if isinstance(item, dict) and text_value(item.get("key"))
        ]
        for key in page_keys:
            if key not in seen:
                seen.add(key)
                keys.append(key)
        start_at += len(page)
        if len(page) < page_size:
            break
        if len(keys) == previous_count:
            raise ValueError(
                "Jira CLI pagination did not advance after "
                f"{len(keys)} Feature(s); results may be truncated. Configure "
                "JIRA_URL and JIRA_TOKEN to retry with cursor-based REST pagination."
            )

    if not keys:
        raise ValueError(f"No Features found for project {project}, Fix Version {version!r}")

    features: list[dict[str, Any]] = []
    for key in keys:
        fetched, issue_bytes = _get_issue_cli(key)
        raw_bytes += issue_bytes
        features.append(_feature(fetched))

    return {
        "mode": "batch",
        "context": slug(version),
        "project": project,
        "fix_version": version,
        "features": features,
        "search_total": None,
        "possibly_truncated": len(keys) >= max_results,
    }, raw_bytes


def _jql_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _status_comment(body: str, author: str) -> bool:
    if author.casefold().strip() not in {"jira", "atlassian"}:
        return False
    return bool(STATUS_COMMENT_RE.fullmatch(body))


def _comments(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    substantive: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        body = text_value(item.get("body"))
        author = text_value(item.get("author"))
        if (
            not body
            or BOT_AUTHOR_RE.search(author)
            or SIZING_COMMENT_RE.search(body)
            or _status_comment(body, author)
        ):
            continue
        if len(body) > MAX_COMMENT_CHARS:
            body = body[: MAX_COMMENT_CHARS - 1].rstrip() + "…"
        created = text_value(item.get("created"))
        substantive.append({"created": created, "body": body})
    # Jira returns comments oldest-first. Retain only the latest few and omit
    # authors because they do not contribute to sizing decisions.
    return substantive[-MAX_COMMENTS:]


def _links(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        linked_fields = item.get("fields")
        if not isinstance(linked_fields, dict):
            linked_fields = {}
        linked_key = text_value(item.get("key"))
        if not linked_key:
            continue
        relationship = text_value(item.get("type")) or "Unknown"
        summary = text_value(linked_fields.get("summary")) or "Unknown"
        result.append({
            "key": linked_key,
            "relationship": relationship,
            "direction": text_value(item.get("direction")),
            "summary": summary,
            "status": text_value(linked_fields.get("status")),
        })
    return result


def _feature(issue: dict[str, Any], *, include_context: bool = True) -> dict[str, Any]:
    fields = issue.get("fields")
    if not isinstance(fields, dict):
        fields = {}
    issue_type = text_value(fields.get("issuetype"))
    feature: dict[str, Any] = {
        "key": text_value(issue.get("key")),
        "title": text_value(fields.get("summary")),
        "issue_type": issue_type,
        "description": text_value(fields.get("description")),
        "status": text_value(fields.get("status")),
        "priority": text_value(fields.get("priority")),
        "fix_versions": [
            text_value(version.get("name"))
            for version in fields.get("fixVersions", [])
            if isinstance(version, dict) and text_value(version.get("name"))
        ] if isinstance(fields.get("fixVersions"), list) else [],
        "current_size": text_value(fields.get("customfield_10795")) or None,
    }
    if include_context:
        feature["comments"] = _comments(issue.get("comments"))
        feature["linked_issues"] = _links(issue.get("links"))
    return feature


def _get_issue(script: Path, key: str) -> dict[str, Any]:
    return _run_fetch(
        script,
        "get",
        key,
        "--fields",
        FIELDS,
        "--comments",
        "--links",
        "--link-fields",
        "summary,status",
    )


def _single(script: Path, key: str) -> tuple[dict[str, Any], int]:
    fetched = _get_issue(script, key)
    feature = _feature(fetched)
    if not feature["key"]:
        feature["key"] = key
    raw_bytes = len(json.dumps(fetched, ensure_ascii=False, indent=2).encode("utf-8"))
    return {
        "mode": "single",
        "context": feature["key"],
        "features": [feature],
    }, raw_bytes


def _release(
    script: Path,
    project: str,
    version: str,
    max_results: int,
) -> tuple[dict[str, Any], int]:
    jql = (
        f"project = {_jql_literal(project)} AND "
        f"fixVersion = {_jql_literal(version)} AND issuetype = Feature"
    )
    search = _run_fetch(
        script,
        "search",
        jql,
        "--fields",
        FIELDS,
        "--max-results",
        str(max_results),
    )
    issues = search.get("issues")
    if not isinstance(issues, list):
        raise ValueError("Jira search returned no issue list")
    if not issues:
        raise ValueError(f"No Features found for project {project}, Fix Version {version!r}")

    features: list[dict[str, Any]] = []
    raw_bytes = len(json.dumps(search, ensure_ascii=False, indent=2).encode("utf-8"))
    for item in issues:
        if not isinstance(item, dict):
            continue
        key = text_value(item.get("key"))
        if not key:
            continue
        fetched = _get_issue(script, key)
        raw_bytes += len(json.dumps(fetched, ensure_ascii=False, indent=2).encode("utf-8"))
        features.append(_feature(fetched))

    total = search.get("total")
    truncated = len(issues) >= max_results or (isinstance(total, int) and total > len(issues))
    return {
        "mode": "batch",
        "context": slug(version),
        "project": project,
        "fix_version": version,
        "features": features,
        "search_total": total if isinstance(total, int) else None,
        "possibly_truncated": truncated,
    }, raw_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch Jira sizing inputs and emit a compact JSON packet."
    )
    parser.add_argument(
        "mode",
        choices=("single", "release"),
        help="Fetch one Feature or a Fix Version batch.",
    )
    parser.add_argument("values", nargs="+", help="ISSUE-KEY, or PROJECT VERSION")
    parser.add_argument(
        "--fetch-script",
        help="Force the shared fetch-issue.py REST helper at this path instead of the configured Jira CLI.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=200,
        help="Maximum Features returned for release mode (default: 200).",
    )
    return parser


def _validated_values(args: argparse.Namespace) -> tuple[str, ...]:
    if args.mode == "single":
        if len(args.values) != 1:
            raise ValueError("single mode requires exactly one issue key")
        key = args.values[0].strip()
        if not ISSUE_KEY_RE.fullmatch(key):
            raise ValueError(f"invalid Jira issue key {args.values[0]!r}; expected PROJECT-123")
        return (key.upper(),)

    if len(args.values) != 2:
        raise ValueError("release mode requires a project key and Fix Version")
    if args.max_results < 1:
        raise ValueError("--max-results must be at least 1")
    return tuple(args.values)


def _fetch(
    mode: str,
    values: tuple[str, ...],
    max_results: int,
    *,
    cli: bool,
    script: Path | None,
) -> tuple[dict[str, Any], int]:
    if cli:
        if mode == "single":
            return _single_cli(values[0])
        return _release_cli(values[0], values[1], max_results)
    if script is None:
        raise ValueError("REST Jira fetch script was not resolved")
    if mode == "single":
        return _single(script, values[0])
    return _release(script, values[0], values[1], max_results)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        values = _validated_values(args)
        use_cli = args.fetch_script is None and shutil.which("jira") is not None
        script = None if use_cli else _fetch_script(args.fetch_script)
        try:
            packet, raw_bytes = _fetch(
                args.mode, values, args.max_results, cli=use_cli, script=script
            )
        except (OSError, ValueError, subprocess.SubprocessError) as cli_error:
            has_rest_credentials = bool(
                os.environ.get("JIRA_URL", "").strip()
                and os.environ.get("JIRA_TOKEN", "").strip()
            )
            if not use_cli or not has_rest_credentials:
                raise
            script = _fetch_script(None)
            print(
                f"Jira CLI fetch failed ({cli_error}); retrying with the REST helper.",
                file=sys.stderr,
            )
            packet, raw_bytes = _fetch(
                args.mode, values, args.max_results, cli=False, script=script
            )
            use_cli = False
        compact = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(compact)
    print(
        f"Prepared {len(packet['features'])} Feature(s) using "
        f"{'Jira CLI' if use_cli else 'the shared REST helper'}; "
        f"payload estimate: {raw_bytes // 4:,} raw to "
        f"{estimate_tokens(compact):,} compact tokens.",
        file=sys.stderr,
    )
    if packet.get("possibly_truncated"):
        print(
            "Warning: Jira search may have reached its result cap; increase --max-results and fetch again.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
