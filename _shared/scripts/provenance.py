#!/usr/bin/env python3
"""Capture and render provenance for prd/design planning document workflows."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKFLOW_DOCS = {
    "prd": "03-prd.md",
    "design": "03-design.md",
}

AUTHORING_PHASES = frozenset({"draft", "revise", "respond", "manual-edit"})

DRIFT_FIELDS = (
    "workflow_version",
    "ai_workflows",
    "source_repo",
    "source_repo_branch",
    "commits_behind_main",
    "commits_ahead_main",
)

PROVENANCE_HEADING = "## Provenance"
PROVENANCE_COMMENT_RE = re.compile(
    r"<!--\s*osac-provenance:(?P<payload>\{.*?\})\s*-->",
    re.DOTALL,
)
LEGACY_FOOTER_RE = re.compile(
    r"\n?---\s*\n+## Provenance\s*\n[\s\S]*?(?=\n---\s*\n|\Z)",
    re.MULTILINE,
)
HEADING_ONLY_FOOTER_RE = re.compile(
    r"\n## Provenance\s*\n[\s\S]*\Z",
    re.MULTILINE,
)
DECLINED_MARKER = (
    '<!-- osac-provenance:{"schema_version":1,"provenance_kind":"declined"} -->'
)
COMMIT_ONLY_NOTE = (
    "> Authoring phases not recorded this session (commit-time snapshot only)."
)


def repo_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_describe(root: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "describe",
                "--always",
                "--dirty= (dirty)",
                "--match=",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown (not a git repository)"


def git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def resolve_main_ref(root: Path) -> str | None:
    candidates = ("origin/HEAD", "origin/main", "origin/master")
    for ref in candidates:
        try:
            subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--verify", ref],
                check=True,
                capture_output=True,
                text=True,
            )
            if ref == "origin/HEAD":
                result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(root),
                        "symbolic-ref",
                        "refs/remotes/origin/HEAD",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return result.stdout.strip().removeprefix("refs/remotes/")
            return ref.removeprefix("origin/")
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None


def main_distance(root: Path) -> tuple[int | None, int | None, str | None]:
    main_ref = resolve_main_ref(root)
    if not main_ref:
        return None, None, None
    remote_ref = main_ref if main_ref.startswith("origin/") else f"origin/{main_ref}"
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "rev-list",
                "--left-right",
                "--count",
                f"{remote_ref}...HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        behind, ahead = result.stdout.strip().split()
        display_ref = remote_ref.removeprefix("origin/")
        return int(behind), int(ahead), display_ref
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None, None, main_ref.removeprefix("origin/")


def workflow_version(ai_root: Path, workflow: str) -> str:
    skill = ai_root / workflow / "SKILL.md"
    if not skill.is_file():
        return "unknown"
    for line in skill.read_text(encoding="utf-8").splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def ai_workflows_root() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    current = Path.cwd()
    for _ in range(32):
        git_root = repo_root(current)
        if git_root:
            return git_root
        if (current / ".artifacts").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


def provenance_path(workflow: str, issue: str) -> Path:
    return workspace_root() / ".artifacts" / workflow / issue / "provenance.json"


def load_provenance(path: Path, workflow: str) -> dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "workflow": workflow,
        "document": WORKFLOW_DOCS[workflow],
        "events": [],
        "drift": {
            "context_changed": False,
            "first_event_index": 0,
            "last_event_index": 0,
            "changed_fields": [],
        },
    }


def compute_drift(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "context_changed": False,
            "first_event_index": 0,
            "last_event_index": 0,
            "changed_fields": [],
        }
    first = events[0]
    last = events[-1]
    changed = [
        field
        for field in DRIFT_FIELDS
        if first.get(field) != last.get(field)
    ]
    return {
        "context_changed": bool(changed),
        "first_event_index": 0,
        "last_event_index": len(events) - 1,
        "changed_fields": changed,
    }


def provenance_kind(events: list[dict[str, Any]]) -> str:
    if not events:
        return "session"
    phases = [event.get("phase") for event in events]
    if all(phase == "commit" for phase in phases):
        return "commit_only"
    return "session"


def capture_event(
    workflow: str,
    issue: str,
    phase: str,
    authoring_mode: str,
) -> None:
    ai_root = ai_workflows_root()
    ws_root = workspace_root()
    path = provenance_path(workflow, issue)
    path.parent.mkdir(parents=True, exist_ok=True)

    behind, ahead, main_label = main_distance(ws_root)
    event: dict[str, Any] = {
        "phase": phase,
        "authoring_mode": authoring_mode,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "workflow_version": workflow_version(ai_root, workflow),
        "ai_workflows": git_describe(ai_root),
        "source_repo": git_describe(ws_root),
        "source_repo_branch": git_branch(ws_root),
    }
    if behind is not None:
        event["commits_behind_main"] = behind
    if ahead is not None:
        event["commits_ahead_main"] = ahead
    if main_label:
        event["main_ref"] = main_label

    data = load_provenance(path, workflow)
    data["events"].append(event)
    data["drift"] = compute_drift(data["events"])
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Captured provenance event: {workflow}/{issue} phase={phase}")


def strip_dirty(hash_value: str) -> tuple[str, bool]:
    return hash_value.replace(" (dirty)", ""), "(dirty)" in hash_value


def format_workspace_suffix(event: dict[str, Any]) -> str:
    parts: list[str] = []
    behind = event.get("commits_behind_main")
    main_ref = event.get("main_ref", "main")
    if behind is not None and behind > 0:
        parts.append(f"{behind} behind origin/{main_ref}")
    source = event.get("source_repo", "")
    if "(dirty)" in source:
        parts.append("dirty")
    if parts:
        return f" ({', '.join(parts)})"
    return ""


def format_event_line(prefix: str, event: dict[str, Any], workflow: str) -> str:
    phase = event.get("phase", "unknown")
    version = event.get("workflow_version", "unknown")
    ai_raw = event.get("ai_workflows", "unknown")
    ai_hash, ai_dirty = strip_dirty(ai_raw)
    branch = event.get("source_repo_branch", "unknown")
    source = event.get("source_repo", "unknown")
    source_hash, _ = strip_dirty(source)
    suffix = format_workspace_suffix(event)
    mode = event.get("authoring_mode")
    mode_suffix = " [manual]" if mode == "manual" else ""
    dirty_suffix = " (dirty)" if ai_dirty else ""
    return (
        f"{prefix}: {phase}{mode_suffix} @ {workflow} {version} - {ai_hash}"
        f"{dirty_suffix}, workspace {branch} @ {source_hash}{suffix}"
    )


def skill_phase_names(events: list[dict[str, Any]]) -> list[str]:
    return [
        event.get("phase", "unknown")
        for event in events
        if event.get("phase") in AUTHORING_PHASES
    ]


def build_metrics_payload(data: dict[str, Any]) -> dict[str, Any]:
    events = data.get("events", [])
    last = events[-1] if events else {}
    drift = data.get("drift", {})
    kind = provenance_kind(events)
    return {
        "schema_version": 1,
        "provenance_kind": kind,
        "workflow": data.get("workflow"),
        "workflow_version": last.get("workflow_version"),
        "ai_workflows": last.get("ai_workflows"),
        "source_repo": last.get("source_repo"),
        "source_repo_branch": last.get("source_repo_branch"),
        "commits_behind_main": last.get("commits_behind_main"),
        "commits_ahead_main": last.get("commits_ahead_main"),
        "main_ref": last.get("main_ref", "main"),
        "phases": [event.get("phase") for event in events],
        "authoring_modes": sorted(
            {event.get("authoring_mode", "skill") for event in events}
        ),
        "context_changed": drift.get("context_changed", False),
    }


def build_footer(data: dict[str, Any]) -> str:
    events = data.get("events", [])
    if not events:
        return ""
    workflow = data.get("workflow", "unknown")
    drift = data.get("drift", {})
    kind = provenance_kind(events)
    metrics = build_metrics_payload(data)
    metrics_comment = (
        f"<!-- osac-provenance:{json.dumps(metrics, separators=(',', ':'))} -->"
    )
    lines = ["---", "", PROVENANCE_HEADING, ""]

    if kind == "commit_only":
        lines.append(format_event_line("Committed", events[-1], workflow))
        lines.append("")
        lines.append(COMMIT_ONLY_NOTE)
    elif drift.get("context_changed") and len(events) > 1:
        lines.append(format_event_line("Authored", events[0], workflow))
        lines.append(format_event_line("Final", events[-1], workflow))
        lines.append("")
        first_phase = events[0].get("phase", "start")
        last_phase = events[-1].get("phase", "end")
        lines.append(f"> Context changed between {first_phase} and {last_phase}.")
    else:
        lines.append(format_event_line("Authored", events[-1], workflow))
        phases = skill_phase_names(events)
        if len(phases) > 1:
            lines.append(f"Phases: {', '.join(phases)}")

    lines.append("")
    lines.append(metrics_comment)
    return "\n".join(lines) + "\n"


def strip_provenance_section(content: str) -> str:
    comment_match = PROVENANCE_COMMENT_RE.search(content)
    if comment_match:
        start = content.rfind("---", 0, comment_match.start())
        if start != -1 and "## Provenance" in content[start:comment_match.end()]:
            return content[:start].rstrip() + "\n"
        stripped = (
            content[: comment_match.start()] + content[comment_match.end() :]
        )
        return stripped.rstrip() + "\n"

    legacy_match = LEGACY_FOOTER_RE.search(content)
    if legacy_match:
        return content[: legacy_match.start()].rstrip() + "\n"

    heading_match = HEADING_ONLY_FOOTER_RE.search(content)
    if heading_match:
        return content[: heading_match.start()].rstrip() + "\n"

    return content.rstrip() + "\n" if content else content


def apply_declined_provenance(content: str) -> str:
    content = strip_provenance_section(content)
    content = PROVENANCE_COMMENT_RE.sub("", content).rstrip() + "\n"
    if DECLINED_MARKER not in content:
        content += "\n" + DECLINED_MARKER + "\n"
    return content


def replace_provenance_section(content: str, footer: str) -> str:
    stripped = strip_provenance_section(content).rstrip()
    if not footer:
        return stripped + "\n" if stripped else ""
    if not stripped.endswith("\n"):
        stripped += "\n"
    return stripped + "\n" + footer


def render_footer(workflow: str, issue: str, target: Path, *, allow_missing: bool = False) -> int:
    if not target.is_file():
        print(f"Error: target file {target} does not exist", file=sys.stderr)
        return 1

    if allow_missing:
        content = apply_declined_provenance(target.read_text(encoding="utf-8"))
        target.write_text(content, encoding="utf-8")
        print(f"Removed provenance footer (declined): {target}")
        return 0

    path = provenance_path(workflow, issue)
    if not path.is_file():
        capture_event(workflow, issue, "commit", "skill")
        print(
            f"Captured commit-time provenance snapshot: {workflow}/{issue}",
            file=sys.stderr,
        )
    else:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if provenance_kind(existing.get("events", [])) == "commit_only":
            capture_event(workflow, issue, "commit", "skill")
            print(
                f"Refreshed commit-time provenance snapshot: {workflow}/{issue}",
                file=sys.stderr,
            )

    data = json.loads(path.read_text(encoding="utf-8"))
    footer = build_footer(data)
    if not footer:
        print("Error: provenance log is empty", file=sys.stderr)
        return 2

    content = target.read_text(encoding="utf-8")
    target.write_text(replace_provenance_section(content, footer), encoding="utf-8")
    print(f"Rendered provenance footer: {target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PRD/design provenance helper")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="Append a provenance event")
    capture.add_argument("--workflow", required=True, choices=sorted(WORKFLOW_DOCS))
    capture.add_argument("--issue", required=True)
    capture.add_argument(
        "--phase",
        required=True,
        choices=["draft", "revise", "respond", "manual-edit", "commit"],
    )
    capture.add_argument(
        "--authoring-mode",
        required=True,
        choices=["skill", "manual"],
    )

    render = sub.add_parser("render", help="Render provenance footer into a file")
    render.add_argument("--workflow", required=True, choices=sorted(WORKFLOW_DOCS))
    render.add_argument("--issue", required=True)
    render.add_argument("--target", required=True, type=Path)
    render.add_argument(
        "--allow-missing",
        action="store_true",
        help="Strip provenance and record declined marker (explicit bypass)",
    )

    args = parser.parse_args()
    if args.command == "capture":
        capture_event(args.workflow, args.issue, args.phase, args.authoring_mode)
        return 0
    if args.command == "render":
        return render_footer(
            args.workflow,
            args.issue,
            args.target,
            allow_missing=args.allow_missing,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
