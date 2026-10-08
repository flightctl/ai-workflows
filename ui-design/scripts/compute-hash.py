#!/usr/bin/env python3
"""Deterministic hash computation for gap_id and content_hash values.

Used by the /review-api and /sync phases to produce stable, reproducible
identifiers for API gaps and content change detection.

Subcommands:
    gap-id      Compute a gap_id from category, data_element, and endpoint.
    content-hash Compute a content_hash from the canonical gap payload fields.

Exit codes:
    0: Success (hash printed to stdout)
    1: Missing or invalid arguments
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys


def compute_gap_id(category: str, data_element: str, endpoint: str) -> str:
    """Compute a stable gap_id.

    Format: {category_slug}-{first 12 hex chars of SHA-256(category|data_element|endpoint)}

    Args:
        category: Gap category (e.g., "data", "field", "state").
        data_element: The "Data Needed" value or UI need description.
        endpoint: The endpoint path, or "N/A" for data gaps with no endpoint.

    Returns:
        The gap_id string (e.g., "field-a1b2c3d4e5f6").
    """
    raw = f"{category}|{data_element}|{endpoint}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    slug = category.lower().replace(" ", "-")
    return f"{slug}-{digest[:12]}"


def compute_content_hash(fields: dict[str, str]) -> str:
    """Compute a canonical content_hash from gap payload fields.

    The hash is SHA-256 of the sorted JSON serialization of the provided
    fields, with all string values trimmed of leading/trailing whitespace.

    Args:
        fields: Dictionary of field name -> value. Expected keys:
            affected_components, category, current_state,
            prd_requirements, severity, suggested_approach, title,
            ui_design_section, ui_need, whats_missing.

    Returns:
        The full SHA-256 hex digest.
    """
    trimmed = {k: v.strip() if isinstance(v, str) else v for k, v in fields.items()}
    payload = json.dumps(trimmed, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cmd_gap_id(args: argparse.Namespace) -> int:
    """Handle the gap-id subcommand."""
    if not args.category or not args.data_element:
        print("error: --category and --data-element are required", file=sys.stderr)
        return 1
    endpoint = args.endpoint or "N/A"
    gap_id = compute_gap_id(args.category, args.data_element, endpoint)
    print(gap_id)
    return 0


def cmd_content_hash(args: argparse.Namespace) -> int:
    """Handle the content-hash subcommand."""
    if args.json_file:
        try:
            with open(args.json_file) as f:
                fields = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read JSON file: {exc}", file=sys.stderr)
            return 1
    elif args.json_stdin:
        try:
            fields = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON on stdin: {exc}", file=sys.stderr)
            return 1
    else:
        # Build from individual flags
        fields = {}
        for key in (
            "affected_components",
            "category",
            "current_state",
            "prd_requirements",
            "severity",
            "suggested_approach",
            "title",
            "ui_design_section",
            "ui_need",
            "whats_missing",
        ):
            val = getattr(args, key.replace("-", "_"), None)
            if val is not None:
                fields[key] = val

    if not fields:
        print("error: no fields provided for content hash", file=sys.stderr)
        return 1

    digest = compute_content_hash(fields)
    print(digest)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic hash computation for API gap tracking."
    )
    subparsers = parser.add_subparsers(dest="command")

    # gap-id subcommand
    gap_parser = subparsers.add_parser(
        "gap-id", help="Compute a gap_id from category, data_element, and endpoint."
    )
    gap_parser.add_argument("--category", required=True, help="Gap category slug")
    gap_parser.add_argument(
        "--data-element", required=True, help="Data element or UI need description"
    )
    gap_parser.add_argument(
        "--endpoint",
        default="N/A",
        help='Endpoint path (default: "N/A" for data gaps)',
    )

    # content-hash subcommand
    hash_parser = subparsers.add_parser(
        "content-hash",
        help="Compute a content_hash from canonical gap payload fields.",
    )
    hash_parser.add_argument(
        "--json-file", help="Read fields from a JSON file"
    )
    hash_parser.add_argument(
        "--json-stdin",
        action="store_true",
        help="Read fields from JSON on stdin",
    )
    # Individual field flags (alternative to JSON input)
    for field in (
        "affected-components",
        "category",
        "current-state",
        "prd-requirements",
        "severity",
        "suggested-approach",
        "title",
        "ui-design-section",
        "ui-need",
        "whats-missing",
    ):
        hash_parser.add_argument(
            f"--{field}", dest=field.replace("-", "_"),
            help=f"Value for the '{field}' field",
        )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "gap-id":
        return cmd_gap_id(args)
    elif args.command == "content-hash":
        return cmd_content_hash(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
