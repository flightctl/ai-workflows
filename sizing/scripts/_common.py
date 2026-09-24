#!/usr/bin/env python3
"""Shared helpers for the deterministic sizing workflow scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SIZES = ("XS", "S", "M", "L", "XL", "XXL")
COMMITTABLE_SIZES = SIZES[:-1]
SIZE_EFFORT = {"XS": 1, "S": 2, "M": 4, "L": 7, "XL": 10}
DIMENSIONS = (
    "scope_breadth",
    "component_surface",
    "integration_surface",
    "novelty",
    "risk_unknowns",
    "testing_surface",
)
TEAMS = ("DEV", "QE", "UX", "UI", "DOCS")
IMPACT_DIMENSIONS = (
    "user_reach",
    "pain_severity",
    "strategic_alignment",
    "dependency",
)


def read_json(path: Path) -> Any:
    """Read JSON from *path* with a concise, actionable error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    """Write stable, readable JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def text_value(value: Any) -> str:
    """Normalize common Jira scalar and option-object values to text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("value", "name", "displayName"):
            item = value.get(key)
            if isinstance(item, str):
                return item.strip()
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def slug(value: str) -> str:
    """Convert a Jira Fix Version name to the existing artifact slug format."""
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "release"


def markdown_cell(value: Any) -> str:
    """Escape content inserted into a Markdown table cell."""
    text = text_value(value).replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|")


def markdown_text(value: Any) -> str:
    """Normalize newlines for Markdown prose without changing punctuation."""
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def estimate_tokens(text: str) -> int:
    """Return a deliberately rough four-characters-per-token estimate."""
    return (len(text.encode("utf-8")) + 3) // 4
