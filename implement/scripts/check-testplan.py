#!/usr/bin/env python3
"""Validate structural mappings between implement plan and story testplan.

Usage: python3 check-testplan.py --plan PATH --testplan PATH [--task NUMBER]
Uses the plan.md and story-testplan.md templates: a four-column Test Plan
Coverage table and '## TC-ID: title' cases with ### Preconditions, Steps,
Expected Results. Supports escaped pipes in table cells. Prints JSON with
selected case bodies for agent reconciliation. No writes or behavioral coverage
claims. Exit: 0 structurally valid/skipped when both absent; 1 invalid/I/O;
2 CLI usage error. Unsupported formats fail rather than guessing.
"""

import argparse
import json
from pathlib import Path
import re
import sys

from plan_helpers import section, sections, tasks, visible_lines

TC = r"TC-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"


def check(plan, testplan, task=None):
    coverage = [s for s in sections(plan, 2) if s[0] == "Test Plan Coverage"]
    if not coverage and testplan is None:
        return {"status": "skipped", "cases": []}
    start, end = section(plan, "Test Plan Coverage")
    if testplan is None:
        raise ValueError("Plan references a missing testplan")
    task_map = tasks(plan)
    if task is not None and task not in task_map:
        raise ValueError(f"Task {task} not found")
    rows = []
    for line in visible_lines(plan[start:end]):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        if cells == ["TC ID", "Title", "Covered by Task", "Notes"]:
            continue
        if cells and all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if len(cells) != 4 or not re.fullmatch(TC, cells[0]):
            raise ValueError(f"Unsupported coverage row: {line.strip()}")
        rows.append(cells)
    if not rows:
        raise ValueError("No coverage rows found")
    cases = {}
    for title, a, b in sections(testplan, 2):
        match = re.fullmatch(f"({TC}): .+", title)
        if not match:
            continue
        tc = match[1]
        if tc in cases:
            raise ValueError(f"Duplicate test case: {tc}")
        body = testplan[a:b]
        for required in ("Preconditions", "Steps", "Expected Results"):
            found = [(x, y) for name, x, y in sections(body, 3) if name == required]
            if len(found) != 1 or not body[found[0][0]:found[0][1]].strip():
                raise ValueError(f"{tc}: missing, empty or duplicate {required}")
        cases[tc] = {"id": tc, "title": title, "body": body.strip()}
    mapped = {}
    selected = []
    for tc, title, owner, notes in rows:
        if tc in mapped:
            raise ValueError(f"Duplicate coverage mapping: {tc}")
        mapped[tc] = owner
        if owner == "N/A":
            if not notes:
                raise ValueError(f"{tc}: N/A requires a rationale")
        else:
            owners = owner.split(",")
            if not all(re.fullmatch(r"Task [1-9][0-9]*", v.strip()) for v in owners):
                raise ValueError(f"{tc}: unsupported task mapping: {owner}")
            numbers = [int(v.strip().split()[1]) for v in owners]
            if any(n not in task_map for n in numbers):
                raise ValueError(f"{tc}: mapping references an unknown task")
            if task is None or task in numbers:
                selected.append(tc)
    if set(mapped) != set(cases):
        raise ValueError(f"TC mismatch: missing cases={sorted(set(mapped) - set(cases))}; "
                         f"unmapped cases={sorted(set(cases) - set(mapped))}")
    return {"status": "structurally-valid", "cases": [cases[tc] for tc in selected],
            "not_applicable": [{"id": r[0], "rationale": r[3]} for r in rows if r[2] == "N/A"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--testplan", type=Path, required=True)
    parser.add_argument("--task", type=int)
    args = parser.parse_args()
    try:
        testplan = args.testplan.read_text() if args.testplan.exists() else None
        print(json.dumps(check(args.plan.read_text(), testplan, args.task), indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
