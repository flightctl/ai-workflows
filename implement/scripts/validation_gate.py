#!/usr/bin/env python3
"""Deterministic validation-freshness gate for the implement workflow.

Checks that a validation report exists, passed, identifies a validated
commit that matches the current HEAD, and that the worktree is clean.
Used by /publish to enforce the validation freshness contract.

Usage:
  validation_gate.py --report PATH
  validation_gate.py --report PATH --expected-sha SHA --remote NAME --branch NAME

Arguments:
  --report PATH         Path to 05-validation-report.md
  --expected-sha SHA    Pushed commit SHA (enables pre-PR remote check)
  --remote NAME         Git remote for live branch verification
  --branch NAME         Branch name for live remote verification

Exit codes:
  0  Gate passed — report is valid PASS for exact current HEAD, worktree clean
  1  Gate failed — prints structured JSON describing the failure reason
  2  Usage error or script crash (not a gate verdict — check stderr)

Output (stdout, exit 0 or 1 only):
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
    """Run a git command and return (returncode, stdout_bytes, stderr)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr.decode("utf-8", errors="replace").strip()


def get_head_sha():
    """Return the full SHA of HEAD, or None on failure."""
    rc, out, _ = run_git("rev-parse", "HEAD")
    if rc != 0 or not out:
        return None
    return out.decode("utf-8").strip()


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
    except UnicodeDecodeError as e:
        info["parse_error"] = f"report is not valid UTF-8: {e}"
        return info
    except OSError as e:
        info["parse_error"] = f"cannot read report: {e}"
        return info

    # --- Result section ---
    result_matches = re.findall(
        r'^## Result\s*\n(.*?)(?=\n## |\Z)',
        content,
        re.MULTILINE | re.DOTALL,
    )
    info["result_count"] = len(result_matches)

    if len(result_matches) == 0:
        _append_error(info, "no '## Result' section found")
    elif len(result_matches) > 1:
        _append_error(info, "multiple '## Result' sections found")
    else:
        first_line = _first_nonempty_line(result_matches[0])
        if first_line is None:
            _append_error(info, "'## Result' section is empty")
        else:
            # Require canonical PASS token: line must start with exactly
            # "PASS" followed by end-of-line, whitespace, or " —"/" -".
            # Rejects PASSING, PASSPORT, PASS123 etc.
            if re.match(r'^PASS(?:\s|$|[^A-Za-z0-9])', first_line):
                info["result_value"] = first_line
            else:
                info["result_value"] = first_line  # store for error msg
                # Not a canonical PASS — will be caught by is_pass check

    # --- Validated Commit section ---
    commit_matches = re.findall(
        r'^## Validated Commit\s*\n(.*?)(?=\n## |\Z)',
        content,
        re.MULTILINE | re.DOTALL,
    )
    info["commit_count"] = len(commit_matches)

    if len(commit_matches) == 0:
        _append_error(info, "no '## Validated Commit' section found")
    elif len(commit_matches) > 1:
        _append_error(info, "multiple '## Validated Commit' sections found")
    else:
        body = commit_matches[0].strip()
        if not body:
            _append_error(info, "'## Validated Commit' section is empty")
        else:
            # Require exactly ONE non-empty line that is a full 40-char
            # hex SHA.  Any extra lines — prose, template placeholders,
            # additional SHAs — are rejected.
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            if len(lines) != 1:
                _append_error(
                    info,
                    f"'## Validated Commit' must contain exactly one "
                    f"non-empty line (found {len(lines)})",
                )
            elif not re.fullmatch(r'[0-9a-f]{40}', lines[0]):
                _append_error(
                    info,
                    f"'## Validated Commit' does not contain a valid "
                    f"40-character SHA (found: {lines[0][:60]!r})",
                )
            else:
                info["validated_commit"] = lines[0]

    return info


def _append_error(info, msg):
    """Append to parse_error, joining with '; '."""
    if info["parse_error"] is None:
        info["parse_error"] = msg
    else:
        info["parse_error"] += f"; {msg}"


def _first_nonempty_line(text):
    """Return the first non-empty stripped line, or None."""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def check_worktree_clean():
    """Check for staged, unstaged, untracked, and submodule changes.

    Uses -z for NUL-delimited output (stable parsing) and
    --ignore-submodules=none to surface dirty submodules regardless of
    config.  Only files reported as ignored (!!) by git are exempt.
    All other entries — including untracked files — are treated as dirty.

    Returns (is_clean, dirty_entries) where dirty_entries is a list of
    human-readable status strings for dirty paths.
    """
    rc, out_bytes, err = run_git(
        "status", "--porcelain", "-z",
        "--untracked-files=normal",
        "--ignore-submodules=none",
    )
    if rc != 0:
        return None, [f"git status failed: {err}"]

    if not out_bytes:
        return True, []

    # Parse NUL-delimited porcelain output.
    # Format: XY<space>PATH<NUL> or XY<space>PATH<NUL>DEST<NUL> for renames
    entries = out_bytes.decode("utf-8", errors="replace").split("\0")

    dirty = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) < 3:
            i += 1
            continue

        xy = entry[:2]
        path = entry[3:]

        # Skip rename destination (consumed as second NUL field)
        if xy[0] == 'R' or xy[0] == 'C':
            i += 2  # skip the "to" path
        else:
            i += 1

        # Only exempt git-ignored entries (!!)
        if xy == "!!":
            continue

        dirty.append(f"{xy} {path}")

    return len(dirty) == 0, dirty


def run_gate(report_path):
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

    # 3. Check Result is canonical PASS
    result_text = report["result_value"] or ""
    is_pass = bool(re.match(r'^PASS(?:\s|$|[^A-Za-z0-9])', result_text))

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
    is_clean, dirty_paths = check_worktree_clean()

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


def run_pre_pr_gate(report_path, expected_sha, remote, branch):
    """Pre-PR publication gate: validates report + HEAD + remote consistency.

    Checks that:
    1. The standard validation gate passes (report PASS, SHA match, clean)
    2. Local HEAD equals expected_sha (the recorded pushed commit)
    3. Live git ls-remote confirms the remote branch points to expected_sha

    Returns a result dict with gate="pass"|"fail".
    """
    # First run the standard gate
    base_result = run_gate(report_path)
    if base_result["gate"] != "pass":
        return base_result

    head = base_result["head"]
    checks = base_result["checks"]

    # Verify HEAD matches expected pushed SHA
    if head != expected_sha:
        checks.append({
            "name": "expected_sha_match",
            "pass": False,
            "detail": f"HEAD={head}, expected={expected_sha}",
        })
        return {
            "gate": "fail",
            "reason": (
                f"HEAD ({head[:12]}) does not match the pushed commit "
                f"({expected_sha[:12]}) — push first or re-validate"
            ),
            "head": head,
            "validated_commit": base_result.get("validated_commit"),
            "checks": checks,
        }

    checks.append({
        "name": "expected_sha_match",
        "pass": True,
        "detail": "ok",
    })

    # Live remote check via git ls-remote
    rc, out_bytes, err = run_git(
        "ls-remote", "--exit-code", remote, f"refs/heads/{branch}",
    )

    if rc != 0:
        detail = f"ls-remote failed (exit {rc}): {err}" if err else \
                 f"ref refs/heads/{branch} not found on {remote}"
        checks.append({
            "name": "remote_branch_match",
            "pass": False,
            "detail": detail,
        })
        return {
            "gate": "fail",
            "reason": f"cannot verify remote branch {branch} on {remote}"
                      f" — {detail}",
            "head": head,
            "validated_commit": base_result.get("validated_commit"),
            "checks": checks,
        }

    # Parse ls-remote output: "<sha>\trefs/heads/<branch>"
    remote_sha = out_bytes.decode("utf-8", errors="replace").split()[0] \
        if out_bytes else ""

    if remote_sha != expected_sha:
        checks.append({
            "name": "remote_branch_match",
            "pass": False,
            "detail": f"remote={remote_sha}, expected={expected_sha}",
        })
        return {
            "gate": "fail",
            "reason": (
                f"remote {remote} branch {branch} points to "
                f"{remote_sha[:12]}, not pushed commit "
                f"{expected_sha[:12]} — push or re-validate"
            ),
            "head": head,
            "validated_commit": base_result.get("validated_commit"),
            "checks": checks,
        }

    checks.append({
        "name": "remote_branch_match",
        "pass": True,
        "detail": "ok",
    })

    return {
        "gate": "pass",
        "head": head,
        "validated_commit": base_result.get("validated_commit"),
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
        "--expected-sha",
        help="Expected pushed commit SHA (enables pre-PR gate mode)",
    )
    parser.add_argument(
        "--remote",
        help="Git remote name for live branch check (required with --expected-sha)",
    )
    parser.add_argument(
        "--branch",
        help="Branch name for live remote check (required with --expected-sha)",
    )
    args = parser.parse_args()

    pre_pr = args.expected_sha is not None
    if pre_pr:
        if not args.remote or not args.branch:
            parser.error("--remote and --branch are required with --expected-sha")
        if not re.fullmatch(r'[0-9a-f]{40}', args.expected_sha):
            parser.error("--expected-sha must be a 40-character hex SHA")

    try:
        if pre_pr:
            result = run_pre_pr_gate(
                args.report, args.expected_sha, args.remote, args.branch,
            )
        else:
            result = run_gate(args.report)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["gate"] == "pass" else 1)
    except Exception as exc:
        # Script crash — not a gate verdict. Print to stderr so callers
        # don't parse it as JSON.
        print(f"validation_gate: internal error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
