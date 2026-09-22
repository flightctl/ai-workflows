#!/usr/bin/env python3
"""Generate a deterministic fallback report synthesis from analyzed data.

The normal /report path asks AI for stakeholder narrative. This helper remains
available as a mechanical fallback when that semantic call cannot be made.

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


def synthesize(data: dict[str, Any]) -> dict[str, Any]:
    issues = [item for item in data["issues"] if isinstance(item, dict)]
    total = len(issues)
    counts = Counter(str(item.get("recommendation") or "UNKNOWN") for item in issues)
    closeable = sum(counts[name] for name in ("CLOSE", "WONT_FIX", "DUPLICATE"))
    closeable_pct = round(closeable / total * 100) if total else 0
    regressions = sum(1 for item in issues if item.get("regressionOf"))
    no_priority = sum(1 for item in issues if not _has_priority(item.get("priority")))
    unassigned = sum(1 for item in issues if not item.get("assignee") or item.get("assignee") == "Unassigned")
    urgent = sum(1 for item in issues if str(item.get("priority", "")).lower() in {"blocker", "critical", "highest", "major", "high"})
    stale = sum(1 for item in issues if _days_since(item.get("updated")) is not None and _days_since(item.get("updated")) >= 90)
    auto_fix = [item for item in issues if item.get("recommendation") == "AUTO_FIX"]
    clusters = [cluster for cluster in data.get("clusters", []) if isinstance(cluster, dict)]

    summary: list[str] = []
    summary.append(f"The backlog contains {total} unresolved bugs; {closeable} ({closeable_pct}%) could be removed through closure, duplicate cleanup, or scope decisions, reducing the active backlog to {total - closeable}." if total else "No unresolved bugs were analyzed.")
    if urgent:
        urgent_clusters = sum(1 for cluster in clusters if any(issue.get("key") in cluster.get("issues", []) and str(issue.get("priority", "")).lower() in {"blocker", "critical", "highest", "major", "high"} for issue in issues))
        summary.append(f"{urgent} bugs have high-severity priority across {urgent_clusters} topic clusters and require immediate attention.")
    if regressions:
        summary.append(f"{regressions} bugs appear related to recently resolved issues and should be checked for regressions.")
    if clusters:
        summary.append(f"{len(clusters)} related clusters cover {sum(len(c.get('issues', [])) for c in clusters)} bugs and may benefit from shared investigation.")
    if stale or no_priority or counts["NEEDS_INFO"] or counts["DUPLICATE"]:
        summary.append(f"Backlog quality signals include {stale} bugs inactive for 90+ days, {no_priority} without priority, {counts['NEEDS_INFO']} needing more information, and {counts['DUPLICATE']} marked duplicate.")
    if auto_fix:
        average = round(sum(item.get("autoFixLikelihood", 0) or 0 for item in auto_fix) / len(auto_fix))
        summary.append(f"{len(auto_fix)} AUTO_FIX candidates have an average estimated success likelihood of {average}%.")
    if total and len(summary) < 3:
        distribution = ", ".join(f"{name}: {counts[name]}" for name in sorted(counts))
        summary.append(f"Recommendation distribution: {distribution}.")
    if total and len(summary) < 3:
        summary.append(f"Triage completeness signals include {unassigned} unassigned bugs and {no_priority} bugs without priority.")
    if not summary:
        summary.append("The analyzed backlog has no material signals to summarize.")

    factors: list[dict[str, str]] = []
    mitigations: list[str] = []
    if regressions >= 5:
        factors.append({"signal": "Open regressions", "severity": "High", "detail": f"{regressions} bugs appear related to recently resolved issues."})
        mitigations.append("Verify the regression candidates before deployment.")
    elif regressions:
        factors.append({"signal": "Possible regressions", "severity": "Medium", "detail": f"{regressions} bugs may represent reappearing resolved problems."})
        mitigations.append("Review the possible regressions against the affected releases.")
    if urgent >= 3:
        factors.append({"signal": "Blocker/Critical backlog", "severity": "High", "detail": f"{urgent} unresolved bugs have the highest priority levels."})
        mitigations.append("Assign owners and address the highest-priority bugs first.")
    if total and no_priority / total > 0.4:
        factors.append({"signal": "Priority blind spot", "severity": "High", "detail": f"{no_priority} of {total} bugs have no assigned priority."})
        mitigations.append("Set priorities for bugs currently missing them.")
    if counts["NEEDS_INFO"]:
        factors.append({"signal": "Incomplete bug reports", "severity": "Medium", "detail": f"{counts['NEEDS_INFO']} bugs lack enough information for confident triage."})
        mitigations.append("Request reproduction steps and impact details for incomplete reports.")
    duplicate_density = counts["DUPLICATE"] / total if total else 0
    if duplicate_density >= 0.2:
        factors.append({"signal": "Duplicate noise", "severity": "Medium", "detail": f"{counts['DUPLICATE']} of {total} bugs ({round(duplicate_density * 100)}%) are marked as duplicates."})
        mitigations.append("Consolidate duplicate reports so engineering effort focuses on unique defects.")
    unowned_urgent = sum(1 for item in issues if str(item.get("priority", "")).lower() in {"blocker", "critical", "highest", "major", "high"} and (not item.get("assignee") or item.get("assignee") == "Unassigned"))
    if unowned_urgent:
        factors.append({"signal": "Unowned high-severity bugs", "severity": "Medium", "detail": f"{unowned_urgent} high-severity bugs have no assignee."})
        mitigations.append("Assign owners to unowned high-severity bugs.")

    if not factors:
        risk_level = "Low"
        risk_summary = "The backlog does not show a material release risk signal based on the available triage data."
    elif any(f["severity"] == "High" for f in factors):
        risk_level = "High"
        risk_summary = "The backlog contains high-severity signals that should be addressed before release."
    else:
        risk_level = "Medium"
        risk_summary = "The backlog contains moderate risk signals that should be reviewed before release."

    return {
        "executiveSummary": summary[:5],
        "releaseRisk": {
            "riskLevel": risk_level,
            "summary": risk_summary,
            "factors": factors,
            "mitigations": mitigations[:5],
        } if total >= 5 else None,
    }


def _days_since(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("+0000", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)


def _has_priority(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"", "undefined", "unassigned", "none", "null"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate fallback triage report synthesis.")
    parser.add_argument("--analyzed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = synthesize(_read(args.analyzed))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Synthesis saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
