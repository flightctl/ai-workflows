#!/usr/bin/env python3
"""Prepare a compact, deterministic input for triage analysis.

The analysis skill should read this output instead of loading the full scan
artifacts.  This script extracts stable signals and candidate matches locally
so the model only has to make the genuinely semantic decisions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_DESCRIPTION = 1800
MAX_CANDIDATES = 3
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "the", "to", "with",
})
ERROR_PATTERNS = (
    (re.compile(r"\b([A-Za-z][\w]*(?:Error|Exception))\b"), "error"),
    (re.compile(r"\b(HTTP\s*[45]\d\d)\b", re.I), "error"),
)
ERROR_CODE_RE = re.compile(r"\b(?:[A-Z]{2,}[_-])?[A-Z]{2,}\d{2,}\b|\b[A-Z]{2,}-\d{3,}\b")
JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
ENVIRONMENT_RE = re.compile(
    r"\b(?:Windows|Linux|macOS|Chrome|Firefox|Safari|Edge|Kubernetes|OpenShift)\b"
    r"|\b(?:version|v)\s*[0-9]+(?:\.[0-9]+){1,3}", re.I,
)
REPRO_RE = re.compile(r"\b(repro(?:duce|duction)?|steps? to reproduce|how to reproduce)\b", re.I)
EXPECTED_RE = re.compile(r"\b(expected|actual|should)\b", re.I)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("issues"), list):
        raise ValueError(f"{path} must contain an object with an issues array")
    return value


def _clean_text(value: Any, limit: int = MAX_DESCRIPTION) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("+0000", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _days_since(value: Any, as_of: datetime) -> int | None:
    parsed = _date(value)
    if parsed is None:
        return None
    return max(0, (as_of - parsed.astimezone(timezone.utc)).days)


def _signature(description: str, summary: str, components: list[str]) -> dict[str, Any]:
    text = f"{summary}\n{description}"
    error_type = None
    for pattern, _ in ERROR_PATTERNS:
        match = pattern.search(text)
        if match:
            error_type = re.sub(r"\s+", " ", match.group(1)).strip()
            break
    code_match = _error_code_match(text)
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    error_excerpt = _clean_text(lines[0] if lines else summary, 240) if error_type or code_match else None
    environment = ENVIRONMENT_RE.search(text)
    return {
        "errorType": error_type,
        "errorCode": code_match.group(0) if code_match else None,
        "errorMessageExcerpt": error_excerpt,
        "affectedComponent": components[0] if components else None,
        "symptoms": _clean_text(summary, 240) or None,
        "environmentHint": environment.group(0) if environment else None,
    }


def _error_code_match(text: str) -> re.Match[str] | None:
    return next(
        (match for match in ERROR_CODE_RE.finditer(text) if not JIRA_KEY_RE.fullmatch(match.group(0))),
        None,
    )


def _compact_issue(issue: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    raw_description = str(issue.get("description") or "")
    description = _clean_text(raw_description)
    summary = _clean_text(issue.get("summary"), 400)
    labels = [str(x) for x in issue.get("labels", []) if x]
    components = [str(x) for x in issue.get("components", []) if x]
    vague = len(description) < 160 and not REPRO_RE.search(description) and not EXPECTED_RE.search(description)
    inactive_days = _days_since(issue.get("updated"), as_of)
    deterministic_recommendation = "CLOSE" if inactive_days is not None and inactive_days >= 365 and vague else None
    result: dict[str, Any] = {
        "key": str(issue.get("key", "")),
        "summary": summary,
        "description": description,
        "status": issue.get("status") or "",
        "priority": issue.get("priority") or "",
        "assignee": issue.get("assignee") or "Unassigned",
        "labels": labels,
        "components": components,
        "created": issue.get("created") or "",
        "updated": issue.get("updated") or "",
        "resolved": issue.get("resolved") or "",
        "ageDays": _days_since(issue.get("created"), as_of),
        "inactiveDays": inactive_days,
        "descriptionSignals": {
            "length": len(description),
            "hasReproduction": bool(REPRO_RE.search(description)),
            "hasExpectedActual": bool(EXPECTED_RE.search(description)),
            "hasErrorDetails": bool(_error_code_match(raw_description) or any(p.search(raw_description) for p, _ in ERROR_PATTERNS)),
        },
        **_signature(raw_description, summary, components),
    }
    if deterministic_recommendation:
        result["deterministicRecommendation"] = deterministic_recommendation
        result["deterministicReason"] = "No activity for at least 12 months and the description lacks reproduction or actionable detail."
    return result


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _add_candidates(items: list[dict[str, Any]], resolved: list[dict[str, Any]]) -> None:
    all_items = [(item, False) for item in items] + [(item, True) for item in resolved]
    tokenized = {item["key"]: _tokens(item["summary"]) for item, _ in all_items}
    for item in items:
        candidates: list[tuple[float, str, str]] = []
        for other, is_resolved in all_items:
            if other["key"] == item["key"]:
                continue
            score = _similarity(tokenized[item["key"]], tokenized[other["key"]])
            if item.get("components") and set(item["components"]) & set(other.get("components", [])):
                score += 0.2
            if item.get("errorType") and item.get("errorType") == other.get("errorType"):
                score += 0.3
            if score >= 0.55:
                candidates.append((score, other["key"], "resolved" if is_resolved else "unresolved"))
        candidates.sort(reverse=True)
        item["matchCandidates"] = [
            {
                "key": key,
                "kind": kind,
                "score": round(min(score, 1.0), 2),
                "summary": next(other["summary"] for other, _ in all_items if other["key"] == key),
                "created": next(other.get("created", "") for other, _ in all_items if other["key"] == key),
                "resolved": next(other.get("resolved", "") for other, _ in all_items if other["key"] == key),
            }
            for score, key, kind in candidates[:MAX_CANDIDATES]
        ]


def prepare(issues_data: dict[str, Any], resolved_data: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    issues = [_compact_issue(item, as_of) for item in issues_data["issues"] if isinstance(item, dict)]
    resolved = [_compact_issue(item, as_of) for item in resolved_data.get("issues", []) if isinstance(item, dict)]
    _add_candidates(issues, resolved)
    return {
        "project": issues_data.get("project", ""),
        "preparedAt": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceCount": len(issues),
        "resolvedCount": len(resolved),
        "issues": issues,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare compact triage analysis input.")
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--resolved", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        resolved_data = _read_json(args.resolved) if args.resolved else {"issues": []}
        result = prepare(_read_json(args.issues), resolved_data, datetime.now(timezone.utc))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Prepared {result['sourceCount']} issues ({result['resolvedCount']} resolved candidates)")
    print(f"Data saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
