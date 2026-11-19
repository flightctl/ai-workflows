#!/usr/bin/env python3
"""Mark one task Done in the implement plan template; preserve all other bytes.

Usage: python3 task-state.py --plan PATH --task NUMBER
Only exact '- **Status:** Pending' or 'Done' lines are supported. Already Done
is an idempotent success. Rejects missing/duplicate tasks or status lines and
pending scope decisions. Does not decide readiness, verify commits, or run git.
Exit: 0 updated/already Done; 1 invalid plan or I/O failure; 2 CLI usage error.
"""

import argparse
from pathlib import Path
import re
import sys
import tempfile

from plan_helpers import sections, tasks, visible_lines


def complete(text, number):
    if any(title == "Pending Scope Decision" for title, _, _ in sections(text, 2)):
        raise ValueError("Resolve Pending Scope Decision before completing a task")
    task_map = tasks(text)
    if number not in task_map:
        raise ValueError(f"Task {number} not found")
    start, end = task_map[number]
    body = "".join(visible_lines(text[start:end]))
    statuses = list(re.finditer(r"^- \*\*Status:\*\* ([^\r\n]+)", body, re.M))
    if len(statuses) != 1 or statuses[0][1] not in ("Pending", "Done"):
        raise ValueError("Expected one exact Pending or Done status in the task")
    match = statuses[0]
    if match[1] == "Done":
        return text
    a, b = start + match.start(1), start + match.end(1)
    return text[:a] + "Done" + text[b:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--task", type=int, required=True)
    args = parser.parse_args()
    temporary = None
    try:
        original = args.plan.read_bytes()
        updated = complete(original.decode("utf-8"), args.task).encode("utf-8")
        if updated != original:
            with tempfile.NamedTemporaryFile(dir=args.plan.parent, delete=False) as out:
                temporary = Path(out.name)
                out.write(updated)
            temporary.chmod(args.plan.stat().st_mode & 0o777)
            if args.plan.read_bytes() != original:
                raise ValueError("Plan changed during update; retry after reading it")
            temporary.replace(args.plan)
        print(f"Task {args.task}: Done")
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
