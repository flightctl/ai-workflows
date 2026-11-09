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

# Script directory — used by tests to locate the CLI entry point
# regardless of the process's current working directory.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_GIT_TIMEOUT = 30  # seconds — bounds network calls (ls-remote) and local ops


def run_git(*args):
    """Run a git command and return (returncode, stdout_bytes, stderr).

    Disables interactive credential prompts and enforces a timeout so
    the gate never hangs in an agent-driven flow.
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, b"", f"git command timed out after {_GIT_TIMEOUT}s"
    return (
        result.returncode,
        result.stdout,
        result.stderr.decode("utf-8", errors="replace").strip(),
    )


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
            info["result_value"] = first_line

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
                    f"40-character lowercase hex SHA "
                    f"(found: {lines[0][:60]!r})",
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

        if xy[0] in ('R', 'C'):
            i += 2
        else:
            i += 1

        if xy == "!!":
            continue

        dirty.append(f"{xy} {path}")

    return len(dirty) == 0, dirty


def _parse_ls_remote_exact(out_bytes, expected_ref):
    """Parse ls-remote output and return SHA for the exact ref match.

    Collects all records whose ref column exactly equals expected_ref.
    Requires exactly one valid 40-char lowercase hex SHA among them.
    Rejects: no match, duplicate/conflicting exact refs, malformed SHA
    on an exact-ref record.  Non-matching refs are ignored.

    Returns (sha, error).  sha is None on error.
    """
    if not out_bytes:
        return None, "empty ls-remote output"
    text = out_bytes.decode("utf-8", errors="replace")
    exact_records = []
    for line in text.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref == expected_ref:
            exact_records.append(sha)

    if not exact_records:
        return None, f"no exact match for {expected_ref} in ls-remote output"

    if len(exact_records) > 1:
        return None, (f"ambiguous: {len(exact_records)} records for "
                      f"{expected_ref}")

    sha = exact_records[0]
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        return None, (f"malformed SHA for {expected_ref}: "
                      f"{sha[:60]!r}")

    return sha, None


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

    report = parse_report(report_path)

    if not report["exists"]:
        checks.append({"name": "report_exists", "pass": False,
                        "detail": "validation report does not exist"})
        return {"gate": "fail",
                "reason": "validation report missing — run /validate",
                "head": head, "checks": checks}

    checks.append({"name": "report_exists", "pass": True, "detail": "ok"})

    if report["parse_error"]:
        checks.append({"name": "report_format", "pass": False,
                        "detail": report["parse_error"]})
        return {"gate": "fail",
                "reason": f"validation report malformed: "
                          f"{report['parse_error']} — run /validate",
                "head": head, "checks": checks}

    checks.append({"name": "report_format", "pass": True, "detail": "ok"})

    result_text = report["result_value"] or ""
    is_pass = bool(re.match(r'^PASS(?:\s|$|[^A-Za-z0-9])', result_text))
    checks.append({"name": "result_pass", "pass": is_pass,
                    "detail": f"result: {result_text[:80]}"
                              if result_text else "empty"})
    if not is_pass:
        return {"gate": "fail",
                "reason": f"validation result is not PASS "
                          f"(found: {result_text[:80]!r}) — run /validate",
                "head": head,
                "validated_commit": report["validated_commit"],
                "checks": checks}

    validated = report["validated_commit"]
    sha_match = validated == head
    checks.append({"name": "sha_match", "pass": sha_match,
                    "detail": f"validated={validated}, head={head}"
                              if not sha_match else "ok"})
    if not sha_match:
        return {"gate": "fail",
                "reason": f"validated commit ({validated[:12]}) does not "
                          f"match HEAD ({head[:12]}) — run /validate",
                "head": head, "validated_commit": validated,
                "checks": checks}

    is_clean, dirty_paths = check_worktree_clean()
    if is_clean is None:
        checks.append({"name": "worktree_clean", "pass": False,
                        "detail": f"check failed: {dirty_paths}"})
        return {"gate": "fail", "reason": "cannot verify worktree state",
                "head": head, "validated_commit": validated,
                "checks": checks}
    checks.append({"name": "worktree_clean", "pass": is_clean,
                    "detail": f"dirty paths: {dirty_paths}"
                              if not is_clean else "ok"})
    if not is_clean:
        return {"gate": "fail",
                "reason": "worktree is not clean — resolve uncommitted "
                          "changes via /code, /implement:review, or "
                          "user-approved /revise, then run /validate",
                "head": head, "validated_commit": validated,
                "checks": checks}

    return {"gate": "pass", "head": head,
            "validated_commit": validated, "checks": checks}


def run_pre_pr_gate(report_path, expected_sha, remote, branch):
    """Pre-PR publication gate: validates report + HEAD + remote consistency.

    Checks that:
    1. The standard validation gate passes (report PASS, SHA match, clean)
    2. Local HEAD equals expected_sha (the recorded pushed commit)
    3. Live git ls-remote confirms the remote branch points to expected_sha

    Returns a result dict with gate="pass"|"fail".
    """
    base_result = run_gate(report_path)
    if base_result["gate"] != "pass":
        return base_result

    head = base_result["head"]
    checks = base_result["checks"]

    if head != expected_sha:
        checks.append({"name": "expected_sha_match", "pass": False,
                        "detail": f"HEAD={head}, expected={expected_sha}"})
        return {"gate": "fail",
                "reason": f"HEAD ({head[:12]}) does not match the pushed "
                          f"commit ({expected_sha[:12]}) — push first or "
                          f"re-validate",
                "head": head,
                "validated_commit": base_result.get("validated_commit"),
                "checks": checks}
    checks.append({"name": "expected_sha_match", "pass": True,
                    "detail": "ok"})

    # Live remote check — use -- to prevent remote name as git option
    expected_ref = f"refs/heads/{branch}"
    rc, out_bytes, err = run_git(
        "ls-remote", "--exit-code", "--", remote, expected_ref,
    )

    if rc != 0:
        detail = (f"ls-remote failed (exit {rc}): {err}" if err
                  else f"ref {expected_ref} not found on {remote}")
        checks.append({"name": "remote_branch_match", "pass": False,
                        "detail": detail})
        return {"gate": "fail",
                "reason": f"cannot verify remote branch {branch} on "
                          f"{remote} — {detail}",
                "head": head,
                "validated_commit": base_result.get("validated_commit"),
                "checks": checks}

    remote_sha, parse_err = _parse_ls_remote_exact(out_bytes, expected_ref)
    if remote_sha is None:
        checks.append({"name": "remote_branch_match", "pass": False,
                        "detail": parse_err})
        return {"gate": "fail",
                "reason": f"cannot verify remote branch {branch} on "
                          f"{remote} — {parse_err}",
                "head": head,
                "validated_commit": base_result.get("validated_commit"),
                "checks": checks}

    if remote_sha != expected_sha:
        checks.append({"name": "remote_branch_match", "pass": False,
                        "detail": f"remote={remote_sha}, "
                                  f"expected={expected_sha}"})
        return {"gate": "fail",
                "reason": f"remote {remote} branch {branch} points to "
                          f"{remote_sha[:12]}, not pushed commit "
                          f"{expected_sha[:12]} — push or re-validate",
                "head": head,
                "validated_commit": base_result.get("validated_commit"),
                "checks": checks}

    checks.append({"name": "remote_branch_match", "pass": True,
                    "detail": "ok"})

    return {"gate": "pass", "head": head,
            "validated_commit": base_result.get("validated_commit"),
            "checks": checks}


def main():
    parser = argparse.ArgumentParser(
        description="Validation freshness gate for /publish",
    )
    parser.add_argument("--report", required=True,
                        help="Path to 05-validation-report.md")
    parser.add_argument("--expected-sha",
                        help="Pushed commit SHA (pre-PR gate mode)")
    parser.add_argument("--remote",
                        help="Git remote for live branch check")
    parser.add_argument("--branch",
                        help="Branch name for live remote check")
    args = parser.parse_args()

    pre_pr = args.expected_sha is not None
    if pre_pr:
        if not args.remote or not args.branch:
            parser.error(
                "--remote and --branch are required with --expected-sha")
        if not re.fullmatch(r'[0-9a-f]{40}', args.expected_sha):
            parser.error("--expected-sha must be a 40-character hex SHA")

    try:
        if pre_pr:
            result = run_pre_pr_gate(
                args.report, args.expected_sha, args.remote, args.branch)
        else:
            result = run_gate(args.report)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["gate"] == "pass" else 1)
    except Exception as exc:
        print(f"validation_gate: internal error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
