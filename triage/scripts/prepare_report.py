#!/usr/bin/env python3
"""Create a compact, deterministic context for semantic report synthesis.

Exit codes: 0 means informational success; 1 means halt due to invalid input.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("issues"), list):
        raise ValueError(f"{path} must contain an object with an issues array")
    return value


def prepare(data: dict[str, Any]) -> dict[str, Any]:
    issues = [item for item in data["issues"] if isinstance(item, dict)]
    compact_issues = []
    for issue in issues:
        compact = {
            "key": issue.get("key"),
            "summary": issue.get("summary"),
            "priority": issue.get("priority"),
            "assignee": issue.get("assignee"),
            "recommendation": issue.get("recommendation"),
            "reason": issue.get("reason"),
            "topic": issue.get("topic"),
            "suggestedPriority": issue.get("suggestedPriority"),
            "priorityMismatch": issue.get("priorityMismatch"),
            "autoFixLikelihood": issue.get("autoFixLikelihood"),
            "duplicateOf": issue.get("duplicateOf"),
            "regressionOf": issue.get("regressionOf"),
            "updated": issue.get("updated"),
            "components": issue.get("components", []),
        }
        updated = issue.get("updated")
        if isinstance(updated, str) and updated:
            try:
                parsed = datetime.fromisoformat(updated.replace("+0000", "+00:00").replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                compact["inactiveDays"] = max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)
            except ValueError:
                compact["inactiveDays"] = None
        else:
            compact["inactiveDays"] = None
        compact_issues.append(compact)
    return {
        "project": data.get("project", ""),
        "totalCount": len(issues),
        "summary": dict(Counter(str(item.get("recommendation") or "UNKNOWN") for item in issues)),
        "clusters": data.get("clusters", []),
        "keyRecommendations": data.get("keyRecommendations", []),
        "issues": compact_issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare compact report-synthesis context.")
    parser.add_argument("--analyzed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(_read(args.analyzed))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Report context saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
