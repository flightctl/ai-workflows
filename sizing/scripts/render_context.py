#!/usr/bin/env python3
"""Validate and render a context artifact, optionally promoting it.

For a valid command, main() returns 0 after rendering and any requested
promotion, or 1 for validation and I/O errors; argparse usage errors exit 2.
Incomplete rollback errors name the recovery directory, which must be preserved.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import markdown_cell, markdown_text, read_json, require_list, require_object, require_string


CONFIDENCE = {"low", "medium", "high"}
INVALIDATED_ARTIFACTS = (
    "02-decisions.json",
    "02-assessment.json",
    "02-assessment.md",
    "03-apply-actions.json",
)


def _string_list(value: Any, label: str) -> list[str]:
    values = require_list(value, label)
    result: list[str] = []
    for index, item in enumerate(values):
        result.append(require_string(item, f"{label}[{index}]"))
    return result


def validate_context(data: Any) -> dict[str, Any]:
    """Validate ``01-context.json``.

    Top-level fields are ``context``, ``mode`` (``single`` or ``batch``), and a
    non-empty ``features`` list; batch metadata may also include ``project``
    and ``fix_version``. Each feature requires ``key``, ``title``,
    ``description_summary``, ``confidence`` (low/medium/high), ``components``
    (each with ``name`` and optional string-list ``paths``), ``data_model``,
    ``testing_surface``, and ``novelty``. Optional fields are string or null
    ``status``, ``priority``, and ``current_size``; string ``comments_summary``;
    string lists ``fix_versions``, ``integrations``, ``concerns``, and
    ``evidence``; and ``linked_issues`` (each with required ``key``,
    ``relationship``, and ``summary``, plus optional string ``status`` and
    ``note``).
    """
    context = require_object(data, "context")
    require_string(context.get("context"), "context.context")
    mode = require_string(context.get("mode"), "context.mode")
    if mode not in {"single", "batch"}:
        raise ValueError("context.mode must be 'single' or 'batch'")
    features = require_list(context.get("features"), "context.features")
    if not features:
        raise ValueError("context.features must contain at least one Feature")

    seen: set[str] = set()
    for index, raw_feature in enumerate(features):
        label = f"context.features[{index}]"
        feature = require_object(raw_feature, label)
        key = require_string(feature.get("key"), f"{label}.key")
        if key in seen:
            raise ValueError(f"duplicate Feature key: {key}")
        seen.add(key)
        require_string(feature.get("title"), f"{label}.title")
        require_string(feature.get("description_summary"), f"{label}.description_summary")
        if feature.get("comments_summary") is not None:
            require_string(feature["comments_summary"], f"{label}.comments_summary", allow_empty=True)

        confidence = require_string(feature.get("confidence"), f"{label}.confidence").lower()
        if confidence not in CONFIDENCE:
            raise ValueError(f"{label}.confidence must be low, medium, or high")
        feature["confidence"] = confidence

        for field in ("status", "priority", "current_size"):
            value = feature.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{label}.{field} must be a string or null")
        for field in ("fix_versions", "integrations", "concerns", "evidence"):
            if field in feature:
                feature[field] = _string_list(feature[field], f"{label}.{field}")

        components = require_list(feature.get("components"), f"{label}.components")
        for component_index, raw_component in enumerate(components):
            component = require_object(raw_component, f"{label}.components[{component_index}]")
            require_string(component.get("name"), f"{label}.components[{component_index}].name")
            component["paths"] = _string_list(
                component.get("paths", []),
                f"{label}.components[{component_index}].paths",
            )

        for field in ("data_model", "testing_surface", "novelty"):
            require_string(feature.get(field), f"{label}.{field}", allow_empty=True)

        linked = require_list(feature.get("linked_issues", []), f"{label}.linked_issues")
        for linked_index, raw_link in enumerate(linked):
            link = require_object(raw_link, f"{label}.linked_issues[{linked_index}]")
            require_string(link.get("key"), f"{label}.linked_issues[{linked_index}].key")
            require_string(link.get("relationship"), f"{label}.linked_issues[{linked_index}].relationship")
            require_string(link.get("summary"), f"{label}.linked_issues[{linked_index}].summary")
            for field in ("status", "note"):
                if link.get(field) is not None and not isinstance(link.get(field), str):
                    raise ValueError(f"{label}.linked_issues[{linked_index}].{field} must be a string")
        feature["linked_issues"] = linked

    return context


def _render_feature(feature: dict[str, Any]) -> list[str]:
    key = markdown_cell(feature["key"])
    title = markdown_cell(feature["title"])
    lines = [
        f"## Feature: {key} — {title}",
        "",
        "### Jira Metadata",
        "",
        f"- **Status:** {markdown_cell(feature.get('status') or '—')}",
        f"- **Priority:** {markdown_cell(feature.get('priority') or '—')}",
        f"- **Fix Version:** {markdown_cell(', '.join(feature.get('fix_versions', [])) or '—')}",
        f"- **Current Size:** {markdown_cell(feature.get('current_size') or 'Not set')}",
        "",
        "### Description Summary",
        "",
        markdown_text(feature["description_summary"]),
        "",
    ]
    if feature.get("comments_summary"):
        lines.extend([
            "### Recent Discussion",
            "",
            markdown_text(feature["comments_summary"]),
            "",
        ])
    lines.extend(["### Codebase Impact", ""])

    components = feature.get("components", [])
    if components:
        component_parts = []
        for item in components:
            paths = ", ".join("`" + path + "`" for path in item["paths"])
            component_parts.append(
                f"{markdown_text(item['name'])} ({paths or 'paths not identified'})"
            )
        component_text = "; ".join(component_parts)
    else:
        component_text = "None identified"
    integrations = ", ".join(markdown_text(item) for item in feature.get("integrations", [])) or "None identified"
    lines.extend([
        f"- **Affected components:** {component_text}",
        f"- **Integration points:** {integrations}",
        f"- **Data model changes:** {markdown_text(feature['data_model']) or 'None identified'}",
        f"- **Testing surface:** {markdown_text(feature['testing_surface']) or 'None identified'}",
        f"- **Novelty assessment:** {markdown_text(feature['novelty']) or 'Uncertain'}",
        f"- **Confidence:** {feature['confidence'].title()}",
    ])

    evidence = feature.get("evidence", [])
    if evidence:
        lines.extend(["", "**Code evidence:**"])
        lines.extend(f"- {markdown_text(item)}" for item in evidence)

    lines.extend(["", "### Linked Issues", ""])
    linked = feature.get("linked_issues", [])
    if linked:
        for item in linked:
            relation = markdown_text(item["relationship"])
            status = markdown_text(item.get("status") or "status unknown")
            note = markdown_text(item.get("note") or "")
            suffix = f" — {note}" if note else ""
            lines.append(
                f"- **{markdown_cell(item['key'])}** ({markdown_cell(relation)}, {markdown_cell(status)}): "
                f"{markdown_text(item['summary'])}{suffix}"
            )
    else:
        lines.append("None.")

    concerns = feature.get("concerns", [])
    if concerns:
        lines.extend(["", "**Concerns:**"])
        lines.extend(f"- {markdown_text(item)}" for item in concerns)
    lines.append("")
    return lines


def render_context(context: dict[str, Any]) -> str:
    mode = "Single Feature" if context["mode"] == "single" else "Batch"
    if context["mode"] == "batch":
        version = context.get("fix_version") or context.get("context")
        mode = f'Batch — Fix Version "{markdown_text(version)}"'
    lines = [
        f"# Sizing Context — {markdown_cell(context['context'])}",
        "",
        "## Input",
        "",
        f"- **Mode:** {mode}",
        f"- **Features:** {len(context['features'])}",
    ]
    if context.get("project"):
        lines.append(f"- **Project:** {markdown_cell(context['project'])}")
    lines.extend(["", "---", ""])
    for feature in context["features"]:
        lines.extend(_render_feature(feature))
        lines.extend(["---", ""])
    return "\n".join(lines).rstrip() + "\n"


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _promote_context(input_json: Path, rendered_markdown: Path, destination: Path) -> None:
    if input_json.name != "01-context.json" or rendered_markdown.name != "01-context.md":
        raise ValueError("staged context files must be named 01-context.json and 01-context.md")

    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    try:
        input_json.resolve().relative_to(destination)
        rendered_markdown.resolve().relative_to(destination)
    except ValueError as exc:
        raise ValueError("staged context files must be inside the destination directory") from exc
    if input_json.resolve().parent == destination:
        raise ValueError("staged context files must be in a temporary subdirectory")
    if not input_json.is_file() or not rendered_markdown.is_file():
        raise ValueError("both staged context files must exist before promotion")

    backup_dir = Path(tempfile.mkdtemp(prefix=".ingest-backup-", dir=destination))
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for name in ("01-context.json", "01-context.md"):
            target = destination / name
            if _exists(target):
                backup = backup_dir / name
                backups.append((backup, target))
                os.replace(target, backup)

        for staged in (input_json, rendered_markdown):
            target = destination / staged.name
            installed.append(target)
            os.replace(staged, target)

        for name in INVALIDATED_ARTIFACTS:
            target = destination / name
            if _exists(target):
                backup = backup_dir / name
                backups.append((backup, target))
                os.replace(target, backup)
    except BaseException as exc:
        rollback_errors: list[OSError] = []
        for target in reversed(installed):
            try:
                target.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(rollback_error)
        for backup, target in reversed(backups):
            if _exists(backup):
                try:
                    os.replace(backup, target)
                except OSError as rollback_error:
                    rollback_errors.append(rollback_error)
        if rollback_errors:
            recovery_error = OSError(
                f"context promotion failed ({exc}); rollback was incomplete, "
                f"preserve recovery files in {backup_dir}"
            )
            if isinstance(exc, Exception):
                raise recovery_error from exc
            raise exc from recovery_error
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise
    else:
        shutil.rmtree(backup_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and render a sizing context JSON artifact.")
    parser.add_argument("input", type=Path, help="Path to 01-context.json")
    parser.add_argument(
        "--commit-to",
        type=Path,
        help="Promote staged context files and invalidate the previous assessment after validation.",
    )
    args = parser.parse_args(argv)
    try:
        context = validate_context(read_json(args.input))
        output = args.input.with_name("01-context.md")
        output.write_text(render_context(context), encoding="utf-8")
        if args.commit_to:
            _promote_context(args.input, output, args.commit_to)
            output = args.commit_to / output.name
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    summary = {
        "context": context["context"],
        "mode": context["mode"],
        "feature_count": len(context["features"]),
        "features": [
            {
                "key": item["key"],
                "current_size": item.get("current_size"),
                "confidence": item["confidence"],
                "components": [component["name"] for component in item["components"]],
            }
            for item in context["features"]
        ],
        "low_confidence_concerns": [
            {"key": item["key"], "concerns": item.get("concerns", [])}
            for item in context["features"]
            if item["confidence"] == "low"
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    print(f"Rendered context saved to {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
