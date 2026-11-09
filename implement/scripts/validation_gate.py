#!/usr/bin/env python3
"""Deterministic validation-freshness gate for the implement workflow.

Checks that a validation report exists, passed, identifies a validated
commit that matches the current HEAD, and that the worktree is clean.
Used by /publish to enforce the validation freshness contract.

Usage:
  validation_gate.py --report PATH [--artifacts-prefix PREFIX]

Arguments:
  --report PATH             Path to 05-validation-report.md
  --artifacts-prefix PREFIX Prefix of paths to ignore in worktree checks
                            (default: .artifacts/)

Exit codes:
  0  Gate passed — report is valid PASS for exact current HEAD, worktree clean
  1  Gate failed — prints structured JSON describing the failure reason
  2  Usage error

Output (stdout):
  JSON object with fields:
    gate:    "pass" | "fail"
    reason:  human-readable explanation (absent when gate=pass)
    head:    current HEAD SHA (always present)
    validated_commit: SHA from report (absent when report missing/malformed)
    checks:  list of individual check results
"""

import argparse
import json
import os
import re
import subprocess
import sys


def run_git(*args):
    """Run a git command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_head_sha():
    """Return the full SHA of HEAD, or None on failure."""
    rc, out, _ = run_git("rev-parse", "HEAD")
    if rc != 0 or not out:
        return None
    return out


def parse_report(report_path):
    """Parse validation report and extract Result and Validated Commit.

    Returns a dict with:
      exists:            bool
      result_value:      str or None  — the text after '## Result' heading
      validated_commit:  str or None  — the SHA after '## Validated Commit'
      result_count:      int          — number of '## Result' sections found
      commit_count:      int          — number of '## Validated Commit' sections
      parse_error:       str or None  — description of parse problem
    """
    info = {
        "exists": False,
        "result_value": None,
        "validated_commit": None,
        "result_count": 0,
        "commit_count": 0,
        "parse_error": None,
    }

    if not os.path.isfile(report_path):
        info["parse_error"] = "report file does not exist"
        return info

    info["exists"] = True

    try:
        with open(report_path, encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        info["parse_error"] = f"cannot read report: {e}"
        return info

    # Extract ## Result sections
    result_matches = re.findall(
        r'^## Result\s*\n(.*?)(?=\n## |\Z)',
        content,
        re.MULTILINE | re.DOTALL,
    )
    info["result_count"] = len(result_matches)

    if len(result_matches) == 0:
        info["parse_error"] = "no '## Result' section found"
    elif len(result_matches) > 1:
        info["parse_error"] = "multiple '## Result' sections found"
    else:
        # Extract first non-empty line as the result value
        for line in result_matches[0].strip().splitlines():
            stripped = line.strip()
            if stripped:
                info["result_value"] = stripped
                break
        if info["result_value"] is None:
            info["parse_error"] = "'## Result' section is empty"

    # Extract ## Validated Commit sections
    commit_matches = re.findall(
        r'^## Validated Commit\s*\n(.*?)(?=\n## |\Z)',
        content,
        re.MULTILINE | re.DOTALL,
    )
    info["commit_count"] = len(commit_matches)

    if len(commit_matches) == 0:
        if info["parse_error"] is None:
            info["parse_error"] = "no '## Validated Commit' section found"
        else:
            info["parse_error"] += "; no '## Validated Commit' section found"
    elif len(commit_matches) > 1:
        err = "multiple '## Validated Commit' sections found"
        if info["parse_error"] is None:
            info["parse_error"] = err
        else:
            info["parse_error"] += f"; {err}"
    else:
        # Extract the SHA — expect a 40-char hex string on its own line
        for line in commit_matches[0].strip().splitlines():
            stripped = line.strip()
            if re.fullmatch(r'[0-9a-f]{40}', stripped):
                info["validated_commit"] = stripped
                break
        if info["validated_commit"] is None:
            # Check for short SHA or other non-full-SHA content
            text = commit_matches[0].strip()
            if text:
                err = (
                    f"'## Validated Commit' does not contain a valid "
                    f"40-character SHA (found: {text[:60]!r})"
                )
            else:
                err = "'## Validated Commit' section is empty"
            if info["parse_error"] is None:
                info["parse_error"] = err
            else:
                info["parse_error"] += f"; {err}"

    return info


def check_worktree_clean(artifacts_prefix):
    """Check for staged, unstaged, and untracked changes.

    Returns (is_clean, dirty_paths) where dirty_paths is a list of
    paths that are dirty, excluding untracked/ignored files under
    artifacts_prefix. Tracked files under artifacts_prefix that show
    as modified ARE reported — only truly untracked artifacts (workflow
    working state in a gitignored directory) are exempt.

    Porcelain status codes:
      '??' = untracked (exempt if under artifacts_prefix)
      '!!' = ignored   (exempt if under artifacts_prefix)
      Any other XY = tracked file change (never exempt)
    """
    rc, out, err = run_git(
        "status", "--porcelain", "--untracked-files=normal",
    )
    if rc != 0:
        return None, [f"git status failed: {err}"]

    if not out:
        return True, []

    dirty = []
    for line in out.splitlines():
        # porcelain format: XY PATH or XY PATH -> PATH
        status_code = line[:2]
        path = line[3:].split(" -> ")[-1].strip()
        if path.startswith(artifacts_prefix):
            # Only exempt untracked (??) or ignored (!!) artifacts.
            # Tracked files under .artifacts/ that show as modified,
            # staged, or deleted are real dirty state.
            if status_code in ("??", "!!"):
                continue
        dirty.append(line.strip())

    return len(dirty) == 0, dirty


def run_gate(report_path, artifacts_prefix=".artifacts/"):
    """Run the full validation gate. Returns a result dict."""
    checks = []
    head = get_head_sha()

    if head is None:
        return {
            "gate": "fail",
            "reason": "cannot determine HEAD SHA",
            "head": None,
            "checks": [{"name": "head_sha", "pass": False,
                         "detail": "git rev-parse HEAD failed"}],
        }

    # 1. Parse the report
    report = parse_report(report_path)

    if not report["exists"]:
        checks.append({
            "name": "report_exists",
            "pass": False,
            "detail": "validation report does not exist",
        })
        return {
            "gate": "fail",
            "reason": "validation report missing — run /validate",
            "head": head,
            "checks": checks,
        }

    checks.append({"name": "report_exists", "pass": True, "detail": "ok"})

    # 2. Check for parse errors (malformed, missing sections, duplicates)
    if report["parse_error"]:
        checks.append({
            "name": "report_format",
            "pass": False,
            "detail": report["parse_error"],
        })
        return {
            "gate": "fail",
            "reason": f"validation report malformed: {report['parse_error']}"
                      " — run /validate",
            "head": head,
            "checks": checks,
        }

    checks.append({"name": "report_format", "pass": True, "detail": "ok"})

    # 3. Check Result is PASS
    result_text = report["result_value"] or ""
    is_pass = result_text.startswith("PASS")

    checks.append({
        "name": "result_pass",
        "pass": is_pass,
        "detail": f"result: {result_text[:80]}" if result_text else "empty",
    })

    if not is_pass:
        return {
            "gate": "fail",
            "reason": f"validation result is not PASS"
                      f" (found: {result_text[:80]!r}) — run /validate",
            "head": head,
            "validated_commit": report["validated_commit"],
            "checks": checks,
        }

    # 4. Check Validated Commit matches HEAD
    validated = report["validated_commit"]
    sha_match = validated == head

    checks.append({
        "name": "sha_match",
        "pass": sha_match,
        "detail": (
            f"validated={validated}, head={head}"
            if not sha_match
            else "ok"
        ),
    })

    if not sha_match:
        return {
            "gate": "fail",
            "reason": (
                f"validated commit ({validated[:12]}) does not match "
                f"HEAD ({head[:12]}) — run /validate"
            ),
            "head": head,
            "validated_commit": validated,
            "checks": checks,
        }

    # 5. Check worktree is clean
    is_clean, dirty_paths = check_worktree_clean(artifacts_prefix)

    if is_clean is None:
        checks.append({
            "name": "worktree_clean",
            "pass": False,
            "detail": f"check failed: {dirty_paths}",
        })
        return {
            "gate": "fail",
            "reason": "cannot verify worktree state",
            "head": head,
            "validated_commit": validated,
            "checks": checks,
        }

    checks.append({
        "name": "worktree_clean",
        "pass": is_clean,
        "detail": (
            f"dirty paths: {dirty_paths}"
            if not is_clean
            else "ok"
        ),
    })

    if not is_clean:
        return {
            "gate": "fail",
            "reason": "worktree is not clean — commit or stash changes, "
                      "then run /validate",
            "head": head,
            "validated_commit": validated,
            "checks": checks,
        }

    # All checks passed
    return {
        "gate": "pass",
        "head": head,
        "validated_commit": validated,
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validation freshness gate for /publish",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to 05-validation-report.md",
    )
    parser.add_argument(
        "--artifacts-prefix",
        default=".artifacts/",
        help="Prefix for paths to ignore in worktree checks (default: .artifacts/)",
    )
    args = parser.parse_args()

    result = run_gate(args.report, args.artifacts_prefix)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["gate"] == "pass" else 1)


if __name__ == "__main__":
    main()
