#!/usr/bin/env python3
"""Merge compact AI decisions with scan data and build report aggregates.

Exit codes: 0 means informational success; 1 means halt due to invalid input
or an invalid AI decision set.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_RECOMMENDATIONS = frozenset({
    "CLOSE", "FIX_NOW", "AUTO_FIX", "BACKLOG", "NEEDS_INFO", "DUPLICATE",
    "ESCALATE", "WONT_FIX",
})
ALLOWED_PRIORITIES = frozenset({
    "Blocker", "Critical", "Highest", "High", "Major", "Medium", "Normal",
    "Low", "Minor", "Lowest", "Trivial",
})


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _decision_map(decisions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values = decisions.get("decisions")
    if not isinstance(values, list):
        raise ValueError("AI decisions must contain a decisions array")
    result: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ValueError("each AI decision must contain an issue key")
        key = item["key"]
        if key in result:
            raise ValueError(f"duplicate AI decision for {key}")
        recommendation = item.get("recommendation")
        if recommendation is not None and recommendation not in ALLOWED_RECOMMENDATIONS:
            raise ValueError(f"invalid recommendation for {key}: {recommendation!r}")
        result[key] = item
    return result


def _fallback_clusters(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        topic = " ".join(str(issue.get("topic") or "").lower().split())
        if topic:
            groups[topic].append(issue)
    clusters: list[dict[str, Any]] = []
    for index, (topic, members) in enumerate(groups.items(), 1):
        if len(members) < 2:
            continue
        cluster_id = f"cluster-{index}"
        for member in members:
            member["clusterId"] = cluster_id
        clusters.append({
            "id": cluster_id,
            "theme": topic,
            "issues": [member["key"] for member in members],
            "suggestedLinkType": "relates to",
            "nextSteps": [f"Investigate the shared {topic} pattern", f"Prioritize the highest-impact issue in {cluster_id}"],
        })
    return clusters


def _fallback_recommendations(issues: list[dict[str, Any]], clusters: list[dict[str, Any]]) -> list[str]:
    counts = Counter(issue.get("recommendation") for issue in issues)
    result: list[str] = []
    urgent = [issue for issue in issues if issue.get("recommendation") in {"FIX_NOW", "AUTO_FIX"}]
    urgent.sort(key=lambda issue: (-_priority_rank(issue.get("priority")), issue.get("key", "")))
    if urgent:
        keys = ", ".join(issue["key"] for issue in urgent[:3])
        result.append(f"Prioritize {keys} ({len(urgent)} urgent or automatable bugs identified).")
    if counts["CLOSE"] or counts["WONT_FIX"] or counts["DUPLICATE"]:
        result.append(f"Clean up {counts['CLOSE'] + counts['WONT_FIX'] + counts['DUPLICATE']} bugs marked for closure, scope decision, or duplicate handling.")
    if clusters:
        largest = max(clusters, key=lambda cluster: len(cluster.get("issues", [])))
        result.append(f"Investigate {len(clusters)} topic clusters; start with {largest.get('id')} ({largest.get('theme')}, {len(largest.get('issues', []))} issues).")
    regressions = sum(1 for issue in issues if issue.get("regressionOf"))
    if regressions:
        result.append(f"Verify {regressions} possible regressions against the corresponding resolved issues.")
    no_priority = sum(1 for issue in issues if not _has_priority(issue.get("priority")))
    if no_priority:
        result.append(f"Set priorities for {no_priority} bugs that currently lack one.")
    stale = sum(1 for issue in issues if _age_days(issue.get("updated")) is not None and _age_days(issue.get("updated")) >= 90)
    if stale:
        result.append(f"Review {stale} bugs with no update in at least 90 days, beginning with the highest-impact items.")
    unassigned_urgent = sum(1 for issue in urgent if not issue.get("assignee") or issue.get("assignee") == "Unassigned")
    if unassigned_urgent:
        result.append(f"Assign owners to {unassigned_urgent} urgent bugs currently unassigned.")
    if counts["NEEDS_INFO"]:
        result.append(f"Request reproduction and impact details for {counts['NEEDS_INFO']} incomplete reports.")
    return result[:10]


def _semantic_clusters(raw: Any, issues: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Validate AI-selected clusters without deriving their meaning in Python."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("AI clusters must be an array")
    issue_keys = {issue["key"] for issue in issues}
    seen: set[str] = set()
    cluster_ids: set[str] = set()
    result: list[dict[str, Any]] = []
    for cluster in raw:
        if not isinstance(cluster, dict) or not isinstance(cluster.get("id"), str):
            raise ValueError("each AI cluster must contain an id")
        cluster_id = cluster["id"]
        if cluster_id in cluster_ids:
            raise ValueError(f"duplicate AI cluster id: {cluster_id}")
        members = cluster.get("issues")
        if not isinstance(members, list) or len(members) < 2 or not all(isinstance(key, str) for key in members):
            raise ValueError(f"AI cluster {cluster_id} must contain at least two issue keys")
        if len(set(members)) != len(members):
            raise ValueError(f"AI cluster {cluster_id} contains a duplicate issue key")
        if any(key not in issue_keys for key in members):
            raise ValueError(f"AI cluster {cluster_id} contains an unknown issue key")
        if seen.intersection(members):
            raise ValueError("AI clusters must not assign an issue to multiple clusters")
        if not isinstance(cluster.get("theme"), str) or not cluster["theme"].strip():
            raise ValueError(f"AI cluster {cluster_id} must contain a theme")
        link_type = cluster.get("suggestedLinkType", "relates to")
        if link_type not in {"relates to", "is caused by", "is duplicated by", "blocks"}:
            raise ValueError(f"invalid link type for AI cluster {cluster_id}")
        next_steps = cluster.get("nextSteps")
        if not isinstance(next_steps, list) or not 2 <= len(next_steps) <= 4 or not all(isinstance(step, str) and step.strip() for step in next_steps):
            raise ValueError(f"AI cluster {cluster_id} must contain 2-4 next steps")
        result.append({"id": cluster_id, "theme": cluster["theme"].strip(), "issues": members,
                       "suggestedLinkType": link_type, "nextSteps": next_steps})
        seen.update(members)
        cluster_ids.add(cluster_id)
    return result


def _semantic_recommendations(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or not 5 <= len(raw) <= 10 or not all(isinstance(item, str) and item.strip() for item in raw):
        raise ValueError("AI keyRecommendations must contain 5-10 non-empty strings")
    return [item.strip() for item in raw]


def _validated_priority_mismatch(raw: Any, original_priority: Any, key: str) -> dict[str, str] | None:
    """Validate the AI's semantic priority-vs-severity judgment."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"priorityMismatch for {key} must be an object or null")
    assigned = raw.get("assigned")
    suggested = raw.get("suggested")
    reason = raw.get("reason")
    if not all(isinstance(value, str) and value.strip() for value in (assigned, suggested, reason)):
        raise ValueError(f"priorityMismatch for {key} must contain assigned, suggested, and reason")
    if not _has_priority(original_priority) or assigned.strip() != str(original_priority).strip():
        raise ValueError(f"priorityMismatch for {key} must match the issue's assigned priority")
    if assigned.strip().lower() == suggested.strip().lower():
        raise ValueError(f"priorityMismatch for {key} must represent a priority change")
    if suggested.strip() not in ALLOWED_PRIORITIES:
        raise ValueError(f"priorityMismatch for {key} has an invalid suggested priority")
    return {"assigned": assigned.strip(), "suggested": suggested.strip(), "reason": reason.strip()}


def _validated_scalar_decisions(decision: dict[str, Any], original_priority: Any, recommendation: str, key: str) -> tuple[str | None, int | None]:
    suggested = decision.get("suggestedPriority")
    has_assigned_priority = _has_priority(original_priority)
    if suggested is not None:
        if not isinstance(suggested, str) or suggested not in ALLOWED_PRIORITIES:
            raise ValueError(f"suggestedPriority for {key} is not a valid Jira priority")
        if has_assigned_priority:
            raise ValueError(f"suggestedPriority for {key} requires a missing Jira priority")

    likelihood = decision.get("autoFixLikelihood")
    if likelihood is not None and (isinstance(likelihood, bool) or not isinstance(likelihood, int) or not 0 <= likelihood <= 100):
        raise ValueError(f"autoFixLikelihood for {key} must be an integer from 0 to 100")
    if recommendation == "AUTO_FIX" and likelihood is None:
        raise ValueError(f"AUTO_FIX decision for {key} requires autoFixLikelihood")
    if recommendation != "AUTO_FIX" and likelihood is not None:
        raise ValueError(f"autoFixLikelihood for {key} is only valid for AUTO_FIX")
    return suggested, likelihood


def _priority_rank(value: Any) -> int:
    return {"blocker": 5, "critical": 4, "highest": 4, "major": 3, "high": 3, "normal": 2, "medium": 2, "minor": 1, "low": 1}.get(str(value or "").lower(), 0)


def _has_priority(value: Any) -> bool:
    return str(value or "").strip().lower() not in {"", "undefined", "unassigned", "none", "null"}


def _age_days(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("+0000", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("+0000", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def finalize(issues_data: dict[str, Any], prepared: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    source = {item.get("key"): item for item in issues_data.get("issues", []) if isinstance(item, dict) and item.get("key")}
    compact = {item.get("key"): item for item in prepared.get("issues", []) if isinstance(item, dict) and item.get("key")}
    mapped = _decision_map(decisions)
    missing = sorted(set(source) - set(mapped))
    unknown = sorted(set(mapped) - set(source))
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing decisions: {', '.join(missing[:10])}")
        if unknown:
            details.append(f"unknown issue keys: {', '.join(unknown[:10])}")
        raise ValueError("AI decision set does not match scan results (" + "; ".join(details) + ")")

    output: list[dict[str, Any]] = []
    for key, original in source.items():
        signal = compact.get(key, {})
        decision = mapped[key]
        recommendation = decision.get("recommendation") or signal.get("deterministicRecommendation")
        if not recommendation:
            raise ValueError(f"AI decision for {key} has no recommendation")
        if not decision.get("reason") and not signal.get("deterministicReason"):
            raise ValueError(f"AI decision for {key} has no reason")
        if decision.get("confidence") not in {"High", "Medium", "Low"}:
            raise ValueError(f"AI decision for {key} has invalid confidence")
        suggested_priority, auto_fix_likelihood = _validated_scalar_decisions(
            decision, original.get("priority"), recommendation, key,
        )
        candidates = {candidate.get("key"): candidate for candidate in signal.get("matchCandidates", [])}
        duplicate_of = decision.get("duplicateOf")
        if duplicate_of is not None:
            if not isinstance(duplicate_of, str) or duplicate_of not in candidates:
                raise ValueError(f"AI duplicate target for {key} was not a supplied candidate")
        regression_of = decision.get("regressionOf")
        if regression_of is not None:
            if (
                not isinstance(regression_of, dict)
                or not isinstance(regression_of.get("key"), str)
                or regression_of["key"] not in candidates
                or candidates[regression_of["key"]].get("kind") != "resolved"
            ):
                raise ValueError(f"AI regression target for {key} was not a supplied resolved candidate")
            resolved_at = _parse_timestamp(candidates[regression_of["key"]].get("resolved"))
            created_at = _parse_timestamp(original.get("created"))
            if resolved_at is None or created_at is None or resolved_at >= created_at:
                raise ValueError(f"AI regression target for {key} has invalid chronology")
        priority_mismatch = _validated_priority_mismatch(decision.get("priorityMismatch"), original.get("priority"), key)
        item = {
            key_name: original.get(key_name)
            for key_name in ("key", "summary", "status", "priority", "assignee", "reporter", "created", "updated", "labels", "components")
        }
        for key_name in ("errorType", "errorCode", "errorMessageExcerpt", "affectedComponent", "symptoms", "environmentHint"):
            item[key_name] = signal.get(key_name)
        item["suggestedPriority"] = suggested_priority
        item["confidence"] = decision.get("confidence")
        item["autoFixLikelihood"] = auto_fix_likelihood
        for key_name in ("duplicateOf", "duplicateConfidence", "regressionOf"):
            item[key_name] = decision.get(key_name)
        item["priorityMismatch"] = priority_mismatch
        item["topic"] = decision.get("topic")
        item["reason"] = decision.get("reason") or signal.get("deterministicReason")
        item["recommendation"] = recommendation
        output.append(item)

    clusters = _semantic_clusters(decisions.get("clusters"), output)
    if clusters is None:
        clusters = _fallback_clusters(output)
    cluster_by_key = {key: cluster["id"] for cluster in clusters for key in cluster["issues"]}
    for item in output:
        item["clusterId"] = cluster_by_key.get(item["key"])
    summary = dict(Counter(item["recommendation"] for item in output))
    recommendations = _semantic_recommendations(decisions.get("keyRecommendations"))
    if recommendations is None:
        recommendations = _fallback_recommendations(output, clusters)
    return {
        "project": issues_data.get("project", ""),
        "analyzedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totalCount": len(output),
        "summary": summary,
        "clusters": clusters,
        "keyRecommendations": recommendations,
        "issues": output,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize triage analysis from compact AI decisions.")
    parser.add_argument("--issues", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = finalize(_read(args.issues), _read(args.prepared), _read(args.decisions))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Analysis finalized: {result['totalCount']} issues")
    print(f"Data saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
