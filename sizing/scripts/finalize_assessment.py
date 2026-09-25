#!/usr/bin/env python3
"""Validate sizing judgments and write the assessment artifacts.

For a valid command, main() returns 0 after both assessment files are written,
or 1 for artifact validation and I/O errors; argparse usage errors exit 2. On
success, a compact summary goes to stdout and the artifact location goes to
stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from _common import (
    DIMENSIONS,
    IMPACT_DIMENSIONS,
    IMPACT_LABELS,
    NO_WORK,
    SIZE_EFFORT,
    SIZES,
    TEAMS,
    markdown_cell,
    markdown_text,
    read_json,
    require_list,
    require_object,
    require_string,
    validate_context_name,
    write_files_transactionally,
)


LEVELS = {"Low", "Medium", "High", "Very High"}
CONFIDENCE = {"low", "medium", "high"}
QUADRANTS = {"Quick Win", "Strategic Bet", "Low-Hanging Fruit", "Reconsider"}
QUADRANT_CHART_SIDES = {
    "Strategic Bet": (True, True),
    "Quick Win": (False, True),
    "Low-Hanging Fruit": (False, False),
    "Reconsider": (True, False),
}
SIZE_RANK = {size: index for index, size in enumerate(SIZES)}
DIMENSION_LABELS = {
    "scope_breadth": "Scope breadth",
    "component_surface": "Component surface",
    "integration_surface": "Integration surface",
    "novelty": "Novelty",
    "risk_unknowns": "Risk/unknowns",
    "testing_surface": "Testing surface",
}


def _optional_text(value: Any, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value.strip()


def _validate_context(context: Any) -> dict[str, Any]:
    root = require_object(context, "context")
    require_string(root.get("context"), "context.context")
    mode = require_string(root.get("mode"), "context.mode")
    if mode not in {"single", "batch"}:
        raise ValueError("context.mode must be 'single' or 'batch'")
    features = require_list(root.get("features"), "context.features")
    if not features:
        raise ValueError("context.features must contain at least one Feature")
    seen: set[str] = set()
    for index, raw in enumerate(features):
        feature = require_object(raw, f"context.features[{index}]")
        key = require_string(feature.get("key"), f"context.features[{index}].key")
        if key in seen:
            raise ValueError(f"duplicate Feature key in context: {key}")
        seen.add(key)
        require_string(feature.get("title"), f"context.features[{index}].title")
    return root


def _decision_map(decisions: Any, context_keys: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Validate the top level of ``02-decisions.json``.

    The object contains a ``features`` array with exactly one decision per
    context key. Optional fields are ``user_overrides`` (feature-key-to-size
    map), ``calibration_notes`` (string), ``capacity_concerns`` (string list),
    and ``defer_notes`` (feature-key-to-string map). Per-feature fields and
    their constraints are defined by ``_validate_feature_decision``.
    """
    root = require_object(decisions, "decisions")
    raw_features = require_list(root.get("features"), "decisions.features")
    result: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_features):
        feature = require_object(raw, f"decisions.features[{index}]")
        key = require_string(feature.get("key"), f"decisions.features[{index}].key")
        if key in result:
            raise ValueError(f"duplicate assessment decision for {key}")
        if key not in context_keys:
            raise ValueError(f"assessment decision references unknown Feature {key}")
        result[key] = feature
    missing = context_keys - result.keys()
    extra = result.keys() - context_keys
    if missing:
        raise ValueError(f"missing assessment decision(s): {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"unexpected assessment decision(s): {', '.join(sorted(extra))}")

    raw_overrides = root.get("user_overrides", {})
    overrides_obj = require_object(raw_overrides, "decisions.user_overrides")
    overrides: dict[str, str] = {}
    for key, value in overrides_obj.items():
        if key not in context_keys:
            raise ValueError(f"user override references unknown Feature {key}")
        size = require_string(value, f"user_overrides.{key}").upper()
        if size not in SIZES:
            raise ValueError(f"invalid user override for {key}: {size}")
        overrides[key] = size

    return result, overrides


def _validate_feature_decision(key: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate one ``02-decisions.json`` feature record.

    Required fields are ``size`` (``SIZES``), ``confidence`` (low/medium/high),
    ``dimensions`` (each name in ``DIMENSIONS`` maps to a level from ``LEVELS``
    and a rationale), ``rationale``, ``teams`` (each name in ``TEAMS`` maps to
    a size from XS–XL or ``—`` and a rationale), and ``impact`` (each name in
    ``IMPACT_DIMENSIONS`` maps to a score from 1–5 and a rationale). Optional
    text fields are ``value_driver``, ``comparison_rationale``, and
    ``quadrant_rationale``; optional ``quadrant`` must be in ``QUADRANTS``.
    ``split_suggestions`` contains ``title``, ``description``, and XS–XL
    ``size``; XXL decisions require 2–3 suggestions.
    """
    label = f"assessment for {key}"
    size = require_string(raw.get("size"), f"{label}.size").upper()
    if size not in SIZES:
        raise ValueError(f"{label}.size must be one of {', '.join(SIZES)}")
    confidence = require_string(raw.get("confidence"), f"{label}.confidence").lower()
    if confidence not in CONFIDENCE:
        raise ValueError(f"{label}.confidence must be low, medium, or high")
    quadrant = _optional_text(raw.get("quadrant"), f"{label}.quadrant")
    if quadrant and quadrant not in QUADRANTS:
        raise ValueError(f"{label}.quadrant is invalid")

    dimensions_raw = require_object(raw.get("dimensions"), f"{label}.dimensions")
    dimensions: dict[str, dict[str, str]] = {}
    for name in DIMENSIONS:
        value = require_object(dimensions_raw.get(name), f"{label}.dimensions.{name}")
        level = require_string(value.get("level"), f"{label}.dimensions.{name}.level")
        if level not in LEVELS:
            raise ValueError(f"{label}.dimensions.{name}.level is invalid")
        rationale = require_string(value.get("rationale"), f"{label}.dimensions.{name}.rationale")
        dimensions[name] = {"level": level, "rationale": rationale}

    teams_raw = require_object(raw.get("teams"), f"{label}.teams")
    teams: dict[str, dict[str, str]] = {}
    for team in TEAMS:
        value = require_object(teams_raw.get(team), f"{label}.teams.{team}")
        team_size = require_string(value.get("size"), f"{label}.teams.{team}.size").upper()
        if team_size not in {*SIZES[:-1], "—"}:
            raise ValueError(f"{label}.teams.{team}.size must be XS–XL or —")
        rationale = _optional_text(value.get("rationale"), f"{label}.teams.{team}.rationale")
        if team_size != "—" and not rationale:
            raise ValueError(f"{label}.teams.{team} needs a specific rationale")
        teams[team] = {"size": team_size, "rationale": rationale}

    impact_raw = require_object(raw.get("impact"), f"{label}.impact")
    impact: dict[str, dict[str, Any]] = {}
    for name in IMPACT_DIMENSIONS:
        value = require_object(impact_raw.get(name), f"{label}.impact.{name}")
        score = value.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            raise ValueError(f"{label}.impact.{name}.score must be an integer from 1 to 5")
        rationale = require_string(value.get("rationale"), f"{label}.impact.{name}.rationale")
        impact[name] = {"score": score, "rationale": rationale}

    splits: list[dict[str, str]] = []
    for index, item in enumerate(require_list(raw.get("split_suggestions", []), f"{label}.split_suggestions")):
        split = require_object(item, f"{label}.split_suggestions[{index}]")
        split_size = require_string(split.get("size"), f"{label}.split_suggestions[{index}].size").upper()
        if split_size not in SIZES[:-1]:
            raise ValueError(f"{label}.split_suggestions[{index}].size must be XS–XL")
        splits.append({
            "title": require_string(split.get("title"), f"{label}.split_suggestions[{index}].title"),
            "description": require_string(split.get("description"), f"{label}.split_suggestions[{index}].description"),
            "size": split_size,
        })
    if size == "XXL" and not 2 <= len(splits) <= 3:
        raise ValueError(f"{label} is XXL and needs 2–3 value-based split suggestions")

    return {
        "size": size,
        "confidence": confidence,
        "dimensions": dimensions,
        "rationale": require_string(raw.get("rationale"), f"{label}.rationale"),
        "teams": teams,
        "impact": impact,
        "value_driver": _optional_text(raw.get("value_driver"), f"{label}.value_driver"),
        "comparison_rationale": _optional_text(raw.get("comparison_rationale"), f"{label}.comparison_rationale"),
        "quadrant": quadrant,
        "quadrant_rationale": _optional_text(raw.get("quadrant_rationale"), f"{label}.quadrant_rationale"),
        "split_suggestions": splits,
    }


def _impact_band(score: int) -> str:
    if score >= 15:
        return "High"
    if score >= 9:
        return "Medium"
    return "Low"


def _quadrant(
    size: str,
    band: str,
    ai_quadrant: str,
    rationale: str,
    key: str,
    *,
    user_override: bool,
) -> tuple[str, str]:
    if size == "XXL":
        return "Must Split", ""
    if size in {"XS", "S"}:
        expected = "Quick Win" if band == "High" else "Low-Hanging Fruit"
        return expected, ""
    if band == "High":
        return "Strategic Bet", ""
    if band == "Low":
        return "Reconsider", ""
    if ai_quadrant not in {"Strategic Bet", "Low-Hanging Fruit"}:
        if user_override:
            return "Strategic Bet", "Recomputed after a user size override using the rubric's Medium/Medium guidance."
        raise ValueError(
            f"assessment for {key} has Medium effort and Medium impact; "
            "set quadrant to Strategic Bet or Low-Hanging Fruit"
        )
    if not rationale:
        if user_override:
            return ai_quadrant, "Recomputed after a user size override using the rubric's Medium/Medium guidance."
        raise ValueError(f"assessment for {key} needs a rationale for its Medium/Medium quadrant")
    return ai_quadrant, rationale


def finalize_assessment(context: Any, decisions: Any) -> dict[str, Any]:
    """Build ``02-assessment.json`` from validated context and decisions.

    Top-level fields are ``context``, ``mode`` (single/batch), ``features``,
    and ``aggregates``.
    Feature records contain ``key``, ``title``, ``current_size``,
    ``recommended_size``, ``original_recommended_size``, ``user_override``,
    ``change``, ``dimensions``, ``rationale``, ``confidence``, ``teams``,
    ``impact``, ``impact_score``, ``impact_band``, ``effort_score``,
    ``priority_score``, ``quadrant``, ``quadrant_rationale``, ``value_driver``,
    ``comparison_rationale``, and ``split_suggestions``. Aggregates contain
    ``size_counts``, ``existing_size_count``, ``matching_size_count``,
    ``disagreement_keys``, ``top_priority_keys``, ``calibration_notes``,
    ``capacity_concerns``, and ``defer_notes``.
    """
    context_obj = _validate_context(context)
    context_features = context_obj["features"]
    by_key = {item["key"]: item for item in context_features}
    raw_decisions = require_object(decisions, "decisions")
    decision_map, overrides = _decision_map(raw_decisions, set(by_key))
    finalized: list[dict[str, Any]] = []

    for source in context_features:
        key = source["key"]
        decision = _validate_feature_decision(key, decision_map[key])
        ai_size = decision["size"]
        size = overrides.get(key, ai_size)
        if ai_size == "XXL" and size != "XXL":
            raise ValueError(
                f"stored override cannot make AI-sized XXL Feature {key} committable; "
                "clear the override and use its split suggestions"
            )
        if size == "XXL" and ai_size != "XXL":
            raise ValueError(f"user override makes {key} XXL; rerun /assess to generate split suggestions")
        impact_score = sum(decision["impact"][name]["score"] for name in IMPACT_DIMENSIONS)
        band = _impact_band(impact_score)
        effort_score = SIZE_EFFORT.get(size)
        priority = round(impact_score / effort_score, 1) if effort_score else None
        quadrant, quadrant_rationale = _quadrant(
            size,
            band,
            decision["quadrant"],
            decision["quadrant_rationale"],
            key,
            user_override=size != ai_size,
        )
        current_size = source.get("current_size")
        current_size = current_size.strip() if isinstance(current_size, str) else ""
        if not current_size:
            change = "new"
            comparison = "No existing size in Jira."
        elif current_size.upper() == size:
            change = "="
            comparison = "Consistent with current Jira value."
        else:
            change = "↑" if SIZE_RANK.get(size, 0) > SIZE_RANK.get(current_size.upper(), 0) else "↓"
            comparison = decision["comparison_rationale"]
            if not comparison:
                if ai_size != current_size.upper():
                    raise ValueError(
                        f"assessment for {key} differs from its Jira size; "
                        "provide comparison_rationale explaining the difference"
                    )
                comparison = f"The user changed the recommended size from {ai_size} to {size}."

        finalized.append({
            "key": key,
            "title": source["title"],
            "current_size": current_size or None,
            "recommended_size": size,
            "original_recommended_size": ai_size if size != ai_size else None,
            "user_override": size != ai_size,
            "change": change,
            "dimensions": decision["dimensions"],
            "rationale": decision["rationale"],
            "confidence": decision["confidence"],
            "teams": decision["teams"],
            "impact": decision["impact"],
            "impact_score": impact_score,
            "impact_band": band,
            "effort_score": effort_score,
            "priority_score": priority,
            "quadrant": quadrant,
            "quadrant_rationale": quadrant_rationale,
            "value_driver": decision["value_driver"],
            "comparison_rationale": comparison,
            "split_suggestions": decision["split_suggestions"] if size == "XXL" else [],
        })

    capacity = require_list(raw_decisions.get("capacity_concerns", []), "decisions.capacity_concerns")
    capacity = [require_string(item, f"decisions.capacity_concerns[{index}]") for index, item in enumerate(capacity)]
    defer_raw = require_object(raw_decisions.get("defer_notes", {}), "decisions.defer_notes")
    defer_notes: dict[str, str] = {}
    for key, note in defer_raw.items():
        if key not in by_key:
            raise ValueError(f"defer note references unknown Feature {key}")
        defer_notes[key] = require_string(note, f"decisions.defer_notes.{key}")

    counts = Counter(item["recommended_size"] for item in finalized)
    existing = [item for item in finalized if item["current_size"]]
    matches = sum(item["change"] == "=" for item in existing)
    disagreements = [item["key"] for item in existing if item["change"] != "="]
    top_priority = sorted(
        (item for item in finalized if item["priority_score"] is not None),
        key=lambda item: (-item["priority_score"], item["key"]),
    )

    return {
        "context": context_obj["context"],
        "mode": context_obj["mode"],
        "features": finalized,
        "aggregates": {
            "size_counts": dict(counts),
            "existing_size_count": len(existing),
            "matching_size_count": matches,
            "disagreement_keys": disagreements,
            "top_priority_keys": [item["key"] for item in top_priority[:4]],
            "calibration_notes": _optional_text(raw_decisions.get("calibration_notes"), "decisions.calibration_notes"),
            "capacity_concerns": capacity,
            "defer_notes": defer_notes,
        },
    }


def _team_size(feature: dict[str, Any], team: str) -> str:
    return feature["teams"][team]["size"]


def _summary_size(feature: dict[str, Any]) -> str:
    size = feature["recommended_size"]
    if feature["user_override"]:
        return f"{size} (overridden from {feature['original_recommended_size']} by user)"
    return size


def _render_quadrant_chart(features: list[dict[str, Any]]) -> list[str]:
    points: list[str] = []
    for feature in features:
        if feature["effort_score"] is None:
            continue
        high_effort, high_impact = QUADRANT_CHART_SIDES[feature["quadrant"]]
        x = (0.55 if high_effort else 0.05) + 0.4 * feature["effort_score"] / 10
        y = (0.55 if high_impact else 0.05) + 0.4 * feature["impact_score"] / 20
        x = min(0.95, max(0.05, x))
        y = min(0.95, max(0.05, y))
        points.append(f"    {feature['key']}: [{x:.2f}, {y:.2f}]")
    return [
        "```mermaid",
        "quadrantChart",
        "    title Impact vs. Effort",
        "    x-axis Low Effort --> High Effort",
        "    y-axis Low Impact --> High Impact",
        "    quadrant-1 Strategic Bet",
        "    quadrant-2 Quick Win",
        "    quadrant-3 Low-Hanging Fruit",
        "    quadrant-4 Reconsider",
        *points,
        "```",
    ]


def _render_summary_table(features: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Summary",
        "",
        "| Feature | Current Size | Recommended Size | Change | Impact Score | Effort Score | Priority | Quadrant | DEV | QE | UX | UI | DOCS |",
        "|---------|-------------|-----------------|--------|--------------|--------------|----------|----------|-----|----|----|----|------|",
    ]
    for feature in features:
        effort = str(feature["effort_score"]) if feature["effort_score"] is not None else "—"
        priority = f"{feature['priority_score']:.1f}" if feature["priority_score"] is not None else "—"
        fields = [
            f"{feature['key']}: {feature['title']}",
            feature["current_size"] or "—",
            _summary_size(feature),
            feature["change"],
            f"{feature['impact_band']} ({feature['impact_score']}/20)",
            effort,
            priority,
            feature["quadrant"],
            *(_team_size(feature, team) for team in TEAMS),
        ]
        lines.append("| " + " | ".join(markdown_cell(value) for value in fields) + " |")
    return lines


def _render_size_distribution(features: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Size Distribution",
        "",
        "| Size | Count | Features |",
        "|------|-------|----------|",
    ]
    for size in reversed(SIZES):
        members = [item for item in features if item["recommended_size"] == size]
        if not members:
            continue
        names = ", ".join(f"{item['key']} ({item['title']})" for item in members)
        lines.append(f"| {size} | {len(members)} | {markdown_cell(names)} |")
    return lines


def _render_highlights(features: list[dict[str, Any]], aggregates: dict[str, Any]) -> list[str]:
    by_key = {item["key"]: item for item in features}
    xxl = [item for item in features if item["recommended_size"] == "XXL"]
    top = [by_key[key] for key in aggregates["top_priority_keys"]]
    strategic = [item for item in features if item["quadrant"] == "Strategic Bet"]
    reconsider = [item for item in features if item["quadrant"] == "Reconsider"]
    low_confidence = [item for item in features if item["confidence"] == "low"]

    lines = ["", "## Key Highlights", "", "**XXL Flags:**"]
    if xxl:
        lines.extend(f"- {item['key']}: {markdown_text(item['title'])} — must be split before committing." for item in xxl)
    else:
        lines.append("None — all Features fit within a single cycle.")

    lines.extend(["", "**Top Priority Scores** (highest impact/effort ratio):"])
    if top:
        for rank, item in enumerate(top, 1):
            note = markdown_text(item["value_driver"] or item["rationale"])
            lines.append(
                f"{rank}. **{item['key']}** — {item['priority_score']:.1f}, "
                f"{item['recommended_size']} effort, {item['impact_band']} impact: {note}"
            )
    else:
        lines.append("No scored Features.")

    lines.extend(["", "**Strategic Bets** (high investment, high return):"])
    if strategic:
        lines.extend(
            f"- **{item['key']}** ({item['priority_score']:.1f}): {markdown_text(item['value_driver'] or item['rationale'])}"
            for item in strategic
        )
    else:
        lines.append("None.")

    lines.extend(["", "**Features in the Reconsider Quadrant:**"])
    if reconsider:
        for item in reconsider:
            defer_note = aggregates["defer_notes"].get(item["key"], "Deferral needs cycle-planning review.")
            lines.append(f"- **{item['key']}** — {markdown_text(defer_note)}")
    else:
        lines.append("None.")

    lines.extend(["", "**Capacity Concerns:**"])
    lines.extend(f"- {markdown_text(item)}" for item in aggregates["capacity_concerns"] or ["None identified."])

    lines.extend(["", "**Low-Confidence Assessments:**"])
    if low_confidence:
        for item in low_confidence:
            lines.append(f"- **{item['key']}** — {markdown_text(item['rationale'])}")
    else:
        lines.append("None.")

    lines.extend(["", "**Jira Size Comparison:**"])
    if aggregates["existing_size_count"]:
        lines.append(
            f"{aggregates['matching_size_count']} of {aggregates['existing_size_count']} existing Jira sizes agree."
        )
        for item in features:
            if item["current_size"] and item["change"] != "=":
                lines.append(f"- **{item['key']}** ({item['current_size']} → {item['recommended_size']}): {markdown_text(item['comparison_rationale'])}")
    else:
        lines.append("None of the Features had existing Jira sizes to compare against.")
    return lines


def _render_feature_detail(feature: dict[str, Any]) -> list[str]:
    lines = [
        "",
        f"## Feature: {markdown_cell(feature['key'])} — {markdown_cell(feature['title'])}",
        "",
        f"### Overall Size: {feature['recommended_size']}",
        "",
        f"**Confidence:** {feature['confidence'].title()}",
        "",
        "**Heuristic Evaluation:**",
        "",
        "| Dimension | Level | Assessment |",
        "|-----------|-------|------------|",
    ]
    for dimension in DIMENSIONS:
        item = feature["dimensions"][dimension]
        lines.append(
            f"| {DIMENSION_LABELS[dimension]} | {item['level']} | {markdown_cell(item['rationale'])} |"
        )
    lines.extend([
        "",
        "**Rationale:**",
        "",
        markdown_text(feature["rationale"]),
        "",
        "### Team Effort Breakdown",
        "",
        "| Team | Effort | Rationale |",
        "|------|--------|-----------|",
    ])
    for team in TEAMS:
        item = feature["teams"][team]
        rationale = item["rationale"] or NO_WORK.get(team, "")
        lines.append(f"| {team} | {item['size']} | {markdown_cell(rationale)} |")
    lines.extend([
        "",
        "### Impact vs. Effort",
        "",
        "| Sub-dimension | Score | Rationale |",
        "|---------------|-------|-----------|",
    ])
    for dimension in IMPACT_DIMENSIONS:
        item = feature["impact"][dimension]
        lines.append(
            f"| {IMPACT_LABELS[dimension]} | {item['score']} | {markdown_cell(item['rationale'])} |"
        )
    effort_text = str(feature["effort_score"]) if feature["effort_score"] is not None else "Not scored (XXL)"
    priority_text = f"{feature['priority_score']:.1f}" if feature["priority_score"] is not None else "Not scored (XXL)"
    lines.extend([
        "",
        f"**Impact Score:** {feature['impact_score']}/20 ({feature['impact_band']})",
        f"**Effort Score:** {effort_text} ({feature['recommended_size']})",
        f"**Priority Score:** {priority_text}",
        f"**Quadrant:** {feature['quadrant']}",
        "",
        "### Jira Comparison",
        "",
        markdown_text(feature["comparison_rationale"]),
    ])
    if feature["quadrant_rationale"]:
        lines.extend(["", f"**Quadrant rationale:** {markdown_text(feature['quadrant_rationale'])}"])
    if feature["recommended_size"] == "XXL":
        lines.extend([
            "",
            "### Split Recommendation",
            "",
            "This Feature must be scoped down before committing to a cycle. Suggested user-value slices:",
            "",
        ])
        for index, split in enumerate(feature["split_suggestions"], 1):
            lines.append(
                f"{index}. **{markdown_cell(split['title'])}:** {markdown_text(split['description'])} — estimated {split['size']}"
            )
    return lines


def render_assessment(assessment: dict[str, Any]) -> str:
    """Render the sections of the ``02-assessment.md`` report."""
    features = assessment["features"]
    aggregates = assessment["aggregates"]
    lines = [
        f"# Sizing Assessment — {markdown_cell(assessment['context'])}",
        "",
        *_render_summary_table(features),
        "",
        "## Impact vs. Effort Map",
        "",
        *_render_quadrant_chart(features),
        "",
    ]
    lines.extend(_render_size_distribution(features))
    lines.extend(_render_highlights(features, aggregates))
    for feature in features:
        lines.extend(_render_feature_detail(feature))
    if assessment["mode"] == "batch":
        calibration = aggregates["calibration_notes"] or "All sizes are internally consistent — no adjustments needed."
        lines.extend(["", "## Relative Calibration Notes", "", markdown_text(calibration)])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finalize and render sizing assessment decisions.")
    parser.add_argument("context_dir", help="Sizing artifact context directory name")
    parser.add_argument(
        "--decisions",
        type=Path,
        help="AI decisions JSON (defaults to 02-decisions.json in the context directory).",
    )
    args = parser.parse_args(argv)
    try:
        validate_context_name(args.context_dir, "context_dir")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    directory = Path(".artifacts") / "sizing" / args.context_dir
    context_path = directory / "01-context.json"
    decisions_path = args.decisions or directory / "02-decisions.json"
    try:
        context = _validate_context(read_json(context_path))
        decisions = read_json(decisions_path)
        assessment = finalize_assessment(context, decisions)
        assessment_json = (
            json.dumps(assessment, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        assessment_markdown = render_assessment(assessment).encode("utf-8")
        write_files_transactionally({
            directory / "02-decisions.json": (
                json.dumps(decisions, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"),
            directory / "02-assessment.json": assessment_json,
            directory / "02-assessment.md": assessment_markdown,
            directory / "03-apply-actions.json": None,
        })
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    summary = {
        "context": assessment["context"],
        "mode": assessment["mode"],
        "features": [
            {
                "key": item["key"],
                "size": item["recommended_size"],
                "impact": item["impact_score"],
                "quadrant": item["quadrant"],
                "priority": item["priority_score"],
                "confidence": item["confidence"],
            }
            for item in assessment["features"]
        ],
        "jira_size_differences": assessment["aggregates"]["disagreement_keys"],
        "capacity_concerns": assessment["aggregates"]["capacity_concerns"],
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    print(f"Assessment files saved in {directory}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
