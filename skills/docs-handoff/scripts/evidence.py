#!/usr/bin/env python3
"""Deterministic delivery-evidence operations for the docs-handoff skill.

Provides subcommands for validating DOCS issue structure, extracting
contributor references, normalizing PR evidence, building bounded
change plans, and checking enrichment idempotency.

Subcommands:
  validate         Validate a DOCS issue snapshot and extract contributors.
  normalize        Normalize and deduplicate raw PR evidence items.
  build-plan       Build a delivery-evidence change plan from validation
                   and normalized evidence.
  check-enrichment Check proposed enrichment against current issue state;
                   with --readback, verify writes and produce receipts.

All inputs are read from JSON files specified via ``--input`` (and
optionally ``--readback``).  This script never contacts Jira, GitHub,
or any external service.  ``urllib.parse`` is used for URL parsing
only -- no network I/O.

Exit codes:
  0 -- success (result JSON on stdout)
  1 -- input validation error or data inconsistency (diagnostic on
       stderr; structured JSON is still written to stdout when the
       error is representable as a result object, e.g. validate
       with invalid issue)
  2 -- invalid arguments (from argparse)
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERROR = 1

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fail(msg: str, code: int = EXIT_ERROR) -> NoReturn:
    """Print an error to stderr and exit."""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def _load_json(path: Path) -> Any:
    """Load and return parsed JSON from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")


def _write_json(data: Any) -> None:
    """Write JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# URL validation  (C)
# ---------------------------------------------------------------------------

# Supported PR/MR URL path patterns.  The path must be EXACTLY a PR/MR
# page — trailing paths (files, commits, checks) are rejected so the
# identity is unambiguous.
#
# GitHub:  /owner/repo/pull/N
# GitLab:  /owner[/subgroup]*/repo/-/merge_requests/N
# GitLab (legacy):  /owner[/subgroup]*/repo/merge_requests/N
_GITHUB_PR_PATH = re.compile(
    r"^/([^/]+)/([^/]+)/pull/(\d+)$"
)
_GITLAB_MR_PATH = re.compile(
    r"^/(.+?)/([^/]+)/-/merge_requests/(\d+)$"
)
_GITLAB_MR_LEGACY_PATH = re.compile(
    r"^/(.+?)/([^/]+)/merge_requests/(\d+)$"
)


def validate_url(url: str, label: str = "url") -> str:
    """Validate an HTTP(S) URL without embedded credentials.

    Returns the normalized URL (trailing slash stripped) or raises
    ValueError with a descriptive message.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{label}: must be a non-empty string")
    url = url.strip()

    if any(ord(c) < 32 or c.isspace() for c in url):
        raise ValueError(f"{label}: contains whitespace or control characters")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"{label}: must use http or https scheme")
    if not parsed.hostname:
        raise ValueError(f"{label}: missing hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{label}: must not contain embedded credentials")
    # Reject explicit non-standard ports — they are unusual for forges
    # and could indicate a local proxy / test fixture that should use
    # .example or .invalid TLDs instead.
    if parsed.port is not None:
        raise ValueError(f"{label}: explicit port not supported for PR URLs")

    normalized = url.rstrip("/")
    return normalized


def validate_pr_url(url: str, label: str = "pr_url") -> str:
    """Validate and normalize a pull/merge-request URL.

    Requires a complete, supported PR/MR path with a numeric
    identifier.  Strips query strings and fragments for identity
    normalization.  Raises ValueError for unrecognized, malformed,
    or trailing-garbage URLs.
    """
    normalized = validate_url(url, label)
    parsed = urlsplit(normalized)
    # Reconstruct with only scheme + authority + path (strip query/fragment)
    clean_path = parsed.path.rstrip("/")
    clean = f"{parsed.scheme}://{parsed.netloc}{clean_path}"

    # Verify the path matches a supported PR/MR structure
    if not (_GITHUB_PR_PATH.match(clean_path)
            or _GITLAB_MR_PATH.match(clean_path)
            or _GITLAB_MR_LEGACY_PATH.match(clean_path)):
        raise ValueError(
            f"{label}: not a recognized PR/MR URL "
            f"(requires /owner/repo/pull/N or "
            f"/owner/repo/-/merge_requests/N): {url}"
        )
    return clean


def extract_pr_identity(url: str) -> dict[str, str]:
    """Extract owner, repo, and PR number from a normalized PR URL.

    Returns a dict with ``owner``, ``repo``, ``number``, ``host``.
    Raises ValueError if the URL does not match a supported forge
    pattern with a numeric identifier.
    """
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")

    m = _GITHUB_PR_PATH.match(path)
    if m:
        return {
            "host": parsed.hostname or "",
            "owner": m.group(1),
            "repo": m.group(2),
            "number": m.group(3),
        }

    m = _GITLAB_MR_PATH.match(path)
    if m:
        return {
            "host": parsed.hostname or "",
            "owner": m.group(1),
            "repo": m.group(2),
            "number": m.group(3),
        }

    m = _GITLAB_MR_LEGACY_PATH.match(path)
    if m:
        return {
            "host": parsed.hostname or "",
            "owner": m.group(1),
            "repo": m.group(2),
            "number": m.group(3),
        }

    raise ValueError(f"unrecognized PR/MR URL structure: {url}")


# ---------------------------------------------------------------------------
# Jira key and reference parsing
# ---------------------------------------------------------------------------

_JIRA_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_STORY_REF_RE = re.compile(
    r"(?:Stories|Story)\s+(\d+\.\d+(?:\s*,\s*\d+\.\d+)*)"
)


def parse_jira_key(text: str) -> str | None:
    """Extract a single Jira key from text, or None."""
    m = _JIRA_KEY_RE.search(text)
    return m.group(1) if m else None


def extract_all_jira_keys(text: str) -> list[str]:
    """Extract all Jira keys from text, preserving order, deduplicated."""
    seen: set[str] = set()
    result: list[str] = []
    for m in _JIRA_KEY_RE.finditer(text):
        key = m.group(1)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def extract_story_refs(text: str) -> list[str]:
    """Extract Story N.NN qualified references from text.

    Returns deduplicated list of qualified IDs like ``story-1.01``.
    """
    seen: set[str] = set()
    result: list[str] = []
    for m in _STORY_REF_RE.finditer(text):
        for part in m.group(1).split(","):
            part = part.strip()
            if part:
                qid = f"story-{part}"
                if qid not in seen:
                    seen.add(qid)
                    result.append(qid)
    return result


# ---------------------------------------------------------------------------
# DOCS issue validation and contributor extraction  (A, B)
# ---------------------------------------------------------------------------

_DOCS_SECTIONS = {
    "Documentation Inputs",
    "Documentation Scope",
    "Acceptance Criteria",
}


def _extract_sections(text: str) -> dict[str, str]:
    """Extract ## sections from rendered Jira markdown description."""
    sections: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []

    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = stripped[3:].strip()
            lines = []
        elif current is not None:
            lines.append(raw)

    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def _extract_contributing_stories(description: str) -> list[str]:
    """Extract Contributing stories references from a rendered description."""
    result: list[str] = []
    seen: set[str] = set()
    for line in description.splitlines():
        stripped = line.strip()
        for pfx in ("- ", "* ", "+ "):
            if stripped.startswith(pfx):
                stripped = stripped[len(pfx):].strip()
                break
        if not stripped.lower().startswith("contributing stories:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        for key in extract_all_jira_keys(value):
            if key not in seen:
                seen.add(key)
                result.append(key)
        for qid in extract_story_refs(value):
            if qid not in seen:
                seen.add(qid)
                result.append(qid)
    return result


def _extract_dependencies(description: str) -> list[str]:
    """Extract Dependencies references from a rendered description."""
    sections = _extract_sections(description)
    deps_text = sections.get("Dependencies", "")
    if not deps_text:
        for line in description.splitlines():
            stripped = line.strip()
            for pfx in ("- ", "* ", "+ "):
                if stripped.startswith(pfx):
                    stripped = stripped[len(pfx):].strip()
                    break
            if stripped.lower().startswith("dependencies:"):
                deps_text = stripped.split(":", 1)[1].strip()
                break

    result: list[str] = []
    seen: set[str] = set()
    for key in extract_all_jira_keys(deps_text):
        if key not in seen:
            seen.add(key)
            result.append(key)
    for qid in extract_story_refs(deps_text):
        if qid not in seen:
            seen.add(qid)
            result.append(qid)
    return result


def _parse_documentation_inputs(text: str) -> list[dict[str, Any]]:
    """Parse Documentation Inputs section into structured items.

    Recognizes bold contributor headers followed by bullet-pointed
    input items.  Each input may carry ``[Assumption]`` or
    ``[Open: ...]`` markers which are preserved.
    """
    items: list[dict[str, Any]] = []
    current_contributor: str | None = None
    contributor_key: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        header_match = re.match(
            r"\*\*(.+?)(?:\s*(?:--|—)\s*.+?)?\s*:?\*\*:?\s*$",
            stripped,
        )
        if header_match:
            header_text = header_match.group(1).strip()
            key = parse_jira_key(header_text)
            if key:
                contributor_key = key
                current_contributor = header_text
            else:
                refs = extract_story_refs(header_text)
                if refs:
                    contributor_key = refs[0]
                    current_contributor = header_text
                else:
                    contributor_key = header_text
                    current_contributor = header_text
            continue

        bullet_match = re.match(r"[-*+]\s+(.*)", stripped)
        if bullet_match and current_contributor is not None:
            raw_text = bullet_match.group(1).strip()
            marker = "planned"
            open_ref = None
            if "[Assumption]" in raw_text:
                marker = "assumption"
            open_match = re.search(r"\[Open:\s*([^\]]+)\]", raw_text)
            if open_match:
                marker = "open"
                open_ref = open_match.group(1).strip()
            # Preserve the original text including markers
            items.append({
                "contributor": contributor_key,
                "contributor_header": current_contributor,
                "text": raw_text,
                "marker": marker,
                "open_ref": open_ref,
            })
    return items


def validate_issue(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate a DOCS issue snapshot and extract structured data.

    Returns a result with ``valid``, ``errors``, ``warnings``, and
    extracted ``contributors``, ``dependencies``,
    ``documentation_inputs``, ``sections``, ``key``.
    """
    errors: list[str] = []
    warnings: list[str] = []

    key = snapshot.get("key")
    if not key or not isinstance(key, str):
        errors.append("missing or invalid 'key' field")
        key = None
    elif not _JIRA_KEY_RE.fullmatch(key):
        errors.append(f"invalid Jira key format: {key}")

    summary = snapshot.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("missing or empty 'summary' field")
    elif "[DOCS]" not in summary:
        errors.append(
            f"summary does not contain [DOCS] prefix: {summary!r}"
        )

    description = snapshot.get("description", "")
    if not isinstance(description, str) or not description.strip():
        errors.append("missing or empty 'description' field")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "key": key,
            "contributors": [],
            "dependencies": [],
            "documentation_inputs": [],
            "sections": {},
        }

    sections = _extract_sections(description)
    missing_sections = _DOCS_SECTIONS - set(sections.keys())
    for ms in sorted(missing_sections):
        errors.append(f"missing required section: {ms}")

    contributors = _extract_contributing_stories(description)
    unresolved = [c for c in contributors if c.startswith("story-")]
    if unresolved:
        for u in unresolved:
            warnings.append(f"unresolved local reference: {u}")
    if not contributors:
        errors.append("no Contributing stories found in description")

    dependencies = _extract_dependencies(description)

    doc_inputs_text = sections.get("Documentation Inputs", "")
    documentation_inputs = _parse_documentation_inputs(doc_inputs_text)
    if not documentation_inputs and "Documentation Inputs" in sections:
        warnings.append(
            "Documentation Inputs section exists but no structured "
            "items parsed"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "key": key,
        "contributors": contributors,
        "dependencies": dependencies,
        "documentation_inputs": documentation_inputs,
        "sections": {k: v for k, v in sections.items()},
    }


# ---------------------------------------------------------------------------
# Evidence normalization  (A, B, C)
# ---------------------------------------------------------------------------


def normalize_evidence(
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize and deduplicate gathered PR evidence.

    Each evidence item must have ``pr_url`` and ``contributor_key``.
    Optional: ``target_branch``, ``state``, ``title``, ``merged``
    (bool), ``merge_commit``, ``observations`` (list of strings).

    Deduplication merges compatible same-PR records (same URL after
    normalization).  Contradictory ``merged`` or ``target_branch``
    values on the same PR produce a conflict warning — neither
    silently wins.

    Returns ``{"items": [...], "errors": [...], "warnings": [...]}``.
    """
    errors: list[str] = []
    warnings: list[str] = []
    seen_urls: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []

    if not isinstance(evidence_items, list):
        return {
            "items": [],
            "errors": ["evidence must be an array"],
            "warnings": [],
        }

    for i, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            errors.append(f"evidence[{i}]: must be an object")
            continue

        pr_url_raw = item.get("pr_url", "")
        contributor = item.get("contributor_key", "")

        if not contributor or not isinstance(contributor, str):
            errors.append(f"evidence[{i}]: missing contributor_key")
            continue

        # Validate merged is bool or None
        merged_val = item.get("merged")
        if merged_val is not None and not isinstance(merged_val, bool):
            errors.append(
                f"evidence[{i}]: 'merged' must be a boolean or null"
            )
            continue

        try:
            pr_url = validate_pr_url(
                pr_url_raw, f"evidence[{i}].pr_url"
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        # Extract identity — reject if unparseable
        try:
            pr_id = extract_pr_identity(pr_url)
        except ValueError as exc:
            errors.append(
                f"evidence[{i}]: {exc}"
            )
            continue

        # Validate observations is a list of strings
        raw_obs = item.get("observations", [])
        if not isinstance(raw_obs, list):
            errors.append(
                f"evidence[{i}]: 'observations' must be an array"
            )
            continue
        observations: list[str] = []
        obs_valid = True
        for j, ob in enumerate(raw_obs):
            if not isinstance(ob, str):
                errors.append(
                    f"evidence[{i}].observations[{j}]: must be a string"
                )
                obs_valid = False
            else:
                observations.append(ob)
        if not obs_valid:
            continue

        target_branch = item.get("target_branch", "")
        if not isinstance(target_branch, str):
            target_branch = str(target_branch)

        # Deduplicate by normalized URL
        if pr_url in seen_urls:
            existing_idx = seen_urls[pr_url]
            existing = normalized[existing_idx]

            # Merge contributor keys
            if contributor not in existing["contributor_keys"]:
                existing["contributor_keys"].append(contributor)

            # Detect contradictory merged state
            if (merged_val is not None
                    and existing["merged"] is not None
                    and merged_val != existing["merged"]):
                existing["conflicts"] = existing.get("conflicts", [])
                existing["conflicts"].append(
                    f"contradictory merged state: "
                    f"evidence[{existing_idx}]={existing['merged']}, "
                    f"evidence[{i}]={merged_val}"
                )
                warnings.append(
                    f"evidence[{i}]: PR {pr_url} has contradictory "
                    f"merged state with evidence[{existing_idx}]"
                )

            # Detect contradictory target branch
            if (target_branch and existing["target_branch"]
                    and target_branch != existing["target_branch"]):
                existing["conflicts"] = existing.get("conflicts", [])
                existing["conflicts"].append(
                    f"contradictory target_branch: "
                    f"'{existing['target_branch']}' vs '{target_branch}'"
                )
                warnings.append(
                    f"evidence[{i}]: PR {pr_url} has contradictory "
                    f"target_branch with evidence[{existing_idx}]"
                )

            # Merge observations
            for ob in observations:
                if ob not in existing["observations"]:
                    existing["observations"].append(ob)

            warnings.append(
                f"evidence[{i}]: duplicate PR URL {pr_url} "
                f"(merged with evidence[{existing_idx}])"
            )
            continue

        entry: dict[str, Any] = {
            "pr_url": pr_url,
            "contributor_keys": [contributor],
            "pr_identity": pr_id,
            "target_branch": target_branch,
            "state": item.get("state", ""),
            "title": item.get("title", ""),
            "merged": merged_val,
            "merge_commit": item.get("merge_commit", ""),
            "observations": observations,
            "conflicts": [],
        }

        seen_urls[pr_url] = len(normalized)
        normalized.append(entry)

    return {"items": normalized, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Change plan  (A, B, D)
# ---------------------------------------------------------------------------


def _fingerprint(data: Any) -> str:
    """Compute a stable SHA-256 fingerprint of JSON-serializable data."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


# Allowed metadata fields that this skill may propose.  Each entry
# maps a canonical name to a description.  Fields NOT in this catalog
# are rejected — no arbitrary keys become eligible.
_ALLOWED_METADATA = {
    "target_release": "Fix Version or Target Version value from project catalog",
}

# Fields that this skill must NEVER modify.
_FORBIDDEN_FIELDS = frozenset({
    "summary", "description", "status", "assignee",
    "sprint", "parent", "labels", "comment",
    "resolution", "priority", "issuetype",
    "reporter", "components", "fixversions",
})

# Metadata catalog V1 — maps skill-level names to actual Jira fields.
# ``target_release`` is the only authorized access path to the Jira
# ``fixVersions`` field.  Direct use of the raw Jira field name is
# blocked by ``_FORBIDDEN_FIELDS`` to prevent catalog bypass.
_METADATA_CATALOG_V1: dict[str, dict[str, Any]] = {
    "target_release": {
        "jira_field": "fixVersions",
        "jira_field_type": "array",
        "jira_item_schema": {
            "type": "version",
            "id_field": "id",
            "name_field": "name",
        },
        "description": (
            "Fix Version value from project version catalog"
        ),
    },
}


def build_change_plan(
    validation: dict[str, Any],
    evidence: dict[str, Any],
    target: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a delivery-evidence change plan.

    Args:
        validation: output of ``validate_issue`` (validated; errors
            checked here rather than trusting ``valid`` flag)
        evidence: output of ``normalize_evidence``
        target: ``{"release": "...", "target_branch": "...",
                  "issue_key": "..."}``
        profile: optional caller-supplied consumer profile with
            ``readiness_dimensions`` list and optional
            ``readiness_results`` dict and ``allowed_fields`` list

    Returns a plan with ``status`` (``complete``, ``invalid_issue``,
    ``invalid_evidence``), ``issue_key``, ``target``, ``inputs``,
    ``pr_links``, ``metadata``, ``findings``, ``source_proposal``,
    ``readiness``, ``plan_digest``.
    """
    # --- Validate nested shapes rather than trusting flags ---
    val_errors = validation.get("errors")
    if not isinstance(val_errors, list):
        val_errors = []

    if val_errors:
        return {
            "status": "invalid_issue",
            "errors": val_errors,
            "issue_key": validation.get("key"),
            "target": target,
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": [],
            "source_proposal": None,
            "readiness": None,
            "plan_digest": "",
        }

    issue_key = validation.get("key")
    if not issue_key or not isinstance(issue_key, str):
        return {
            "status": "invalid_issue",
            "errors": ["validation result missing valid key"],
            "issue_key": None,
            "target": target,
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": [],
            "source_proposal": None,
            "readiness": None,
            "plan_digest": "",
        }

    if not _JIRA_KEY_RE.fullmatch(issue_key):
        return {
            "status": "invalid_issue",
            "errors": [f"invalid Jira key format: {issue_key}"],
            "issue_key": issue_key,
            "target": target,
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": [],
            "source_proposal": None,
            "readiness": None,
            "plan_digest": "",
        }

    # Validate evidence shape — errors block eligible operations
    ev_errors = evidence.get("errors", [])
    if not isinstance(ev_errors, list):
        ev_errors = []
    if ev_errors:
        return {
            "status": "invalid_evidence",
            "errors": ev_errors,
            "issue_key": issue_key,
            "target": target,
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": [],
            "source_proposal": None,
            "readiness": None,
            "plan_digest": "",
        }
    ev_items = evidence.get("items", [])
    if not isinstance(ev_items, list):
        return {
            "status": "invalid_evidence",
            "errors": ["evidence items must be an array"],
            "issue_key": issue_key,
            "target": target,
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": [],
            "source_proposal": None,
            "readiness": None,
            "plan_digest": "",
        }

    contributors_list = validation.get("contributors", [])
    if not isinstance(contributors_list, list):
        contributors_list = []
    contributors = set(contributors_list)

    deps_list = validation.get("dependencies", [])
    if not isinstance(deps_list, list):
        deps_list = []
    dependencies = set(deps_list)

    doc_inputs = validation.get("documentation_inputs", [])
    if not isinstance(doc_inputs, list):
        doc_inputs = []

    target_release = target.get("release", "")
    target_branch = target.get("target_branch", "")
    findings: list[dict[str, str]] = []

    # --- Index evidence by contributor ---
    contributor_evidence: dict[str, list[dict[str, Any]]] = {}
    for ev in ev_items:
        for ck in ev.get("contributor_keys", []):
            contributor_evidence.setdefault(ck, []).append(ev)

    # --- Contributor coverage (independent of parsed inputs) ---
    all_evidence_contributors: set[str] = set()
    contributor_pr_links: set[str] = set()
    for ev in ev_items:
        for ck in ev.get("contributor_keys", []):
            all_evidence_contributors.add(ck)
            if ck in contributors:
                contributor_pr_links.add(ev["pr_url"])

    # --- Per-input delivery status (B: honest per-input assessment) ---
    input_statuses: list[dict[str, Any]] = []

    for doc_input in doc_inputs:
        contrib = doc_input.get("contributor")
        evs = contributor_evidence.get(contrib, []) if contrib else []

        status = "no_evidence"
        evidence_refs: list[dict[str, Any]] = []
        target_notes: list[str] = []
        input_conflicts: list[str] = []

        if evs:
            for ev in evs:
                ev_merged = ev.get("merged")
                ev_target = ev.get("target_branch", "")
                ev_conflicts = ev.get("conflicts", [])

                # Build per-PR evidence ref
                pr_status = "unknown"
                if ev_conflicts:
                    pr_status = "conflicting"
                    input_conflicts.extend(ev_conflicts)
                elif ev_merged is True:
                    if (target_branch and ev_target
                            and ev_target != target_branch):
                        pr_status = "merged_wrong_target"
                        target_notes.append(
                            f"PR {ev['pr_url']} targets {ev_target}, "
                            f"expected {target_branch}"
                        )
                    else:
                        pr_status = "merged"
                elif ev_merged is False:
                    pr_status = "not_merged"
                # ev_merged is None → unknown

                evidence_refs.append({
                    "pr_url": ev["pr_url"],
                    "pr_status": pr_status,
                    "target_branch": ev_target,
                    "observations": ev.get("observations", []),
                })

            # Determine overall input status from individual PR statuses
            pr_statuses = {r["pr_status"] for r in evidence_refs}
            if "conflicting" in pr_statuses:
                status = "conflicting"
            elif "merged" in pr_statuses:
                status = "merged_pr_exists"
            elif "merged_wrong_target" in pr_statuses:
                status = "merged_wrong_target"
            elif "not_merged" in pr_statuses:
                status = "in_progress"
            else:
                status = "evidence_unverified"

        input_statuses.append({
            "text": doc_input.get("text", ""),
            "contributor": contrib,
            "marker": doc_input.get("marker", "planned"),
            "status": status,
            "evidence_refs": evidence_refs,
            "target_notes": target_notes,
            "conflicts": input_conflicts,
        })

    # --- Contributors without evidence (B: always flag, even if
    # also a dependency) ---
    for contrib in sorted(contributors):
        if contrib not in all_evidence_contributors:
            if contrib.startswith("story-"):
                findings.append({
                    "type": "unresolved_contributor",
                    "ref": contrib,
                    "detail": (
                        f"Contributor {contrib} is an unresolved local "
                        f"reference with no Jira key mapping"
                    ),
                })
            else:
                findings.append({
                    "type": "missing_evidence",
                    "ref": contrib,
                    "detail": (
                        f"Contributing story {contrib} has no "
                        f"associated PR evidence"
                    ),
                })

    # --- Input/contributor alignment ---
    all_contributor_keys: set[str] = set(contributors)
    for di in doc_inputs:
        c = di.get("contributor")
        if c:
            all_contributor_keys.add(c)
            if c not in contributors:
                findings.append({
                    "type": "input_contributor_mismatch",
                    "ref": c,
                    "detail": (
                        f"Documentation input header references {c} "
                        f"which is not listed in Contributing stories"
                    ),
                })

    for ev in ev_items:
        for ck in ev.get("contributor_keys", []):
            if ck not in all_contributor_keys:
                findings.append({
                    "type": "non_contributor_evidence",
                    "ref": ck,
                    "detail": (
                        f"PR {ev['pr_url']} is attributed to {ck} "
                        f"which is not a listed contributor — this is "
                        f"a candidate for scope review, not automatic "
                        f"enrichment"
                    ),
                    "pr_url": ev["pr_url"],
                })

    # --- PR Remote Links: ONLY for actual contributors ---
    pr_links: list[dict[str, Any]] = []
    seen_link_urls: set[str] = set()
    for ev in ev_items:
        url = ev["pr_url"]
        if url in seen_link_urls:
            continue
        # Only include PRs attributed to actual contributors
        if url not in contributor_pr_links:
            continue
        seen_link_urls.add(url)
        pr_links.append({
            "url": url,
            "title": ev.get("title", ""),
            "relationship": "implements",
            "contributor_keys": [
                ck for ck in ev.get("contributor_keys", [])
                if ck in all_contributor_keys
            ],
        })

    # --- Metadata (D: allowed catalog only, real Jira binding) ---
    metadata: dict[str, Any] = {}
    if target_release:
        cat = _METADATA_CATALOG_V1["target_release"]
        metadata["target_release"] = {
            "value": target_release,
            "jira_field": cat["jira_field"],
            "jira_field_type": cat["jira_field_type"],
            "catalog_verified": False,
            "catalog_entry": None,
            "before": None,
            "note": (
                "Requires catalog entry with version ID before apply"
            ),
        }

    # Profile allowed fields — only from catalog
    if profile and isinstance(profile, dict):
        for af in profile.get("allowed_fields", []):
            if not isinstance(af, dict):
                continue
            field_name = af.get("name", "")
            if field_name in _FORBIDDEN_FIELDS:
                findings.append({
                    "type": "forbidden_field",
                    "ref": field_name,
                    "detail": (
                        f"Profile requests field '{field_name}' which "
                        f"is forbidden by policy"
                    ),
                })
            elif field_name in _ALLOWED_METADATA:
                cat = _METADATA_CATALOG_V1.get(field_name, {})
                metadata[field_name] = {
                    "value": af.get("value"),
                    "jira_field": cat.get("jira_field", ""),
                    "jira_field_type": cat.get("jira_field_type", ""),
                    "catalog_verified": af.get(
                        "catalog_verified", False
                    ),
                    "catalog_entry": af.get("catalog_entry"),
                    "before": af.get("before"),
                }

    # --- Readiness (B: independent of delivery, visible gaps) ---
    readiness: dict[str, Any] | None = None
    if profile and isinstance(profile, dict):
        dims = profile.get("readiness_dimensions", [])
        provided_results = profile.get("readiness_results", {})
        if not isinstance(dims, list):
            dims = []
        if not isinstance(provided_results, dict):
            provided_results = {}

        results: dict[str, Any] = {}
        for d in dims:
            if isinstance(d, str) and d in provided_results:
                results[d] = provided_results[d]
            elif isinstance(d, str):
                results[d] = {
                    "assessed": False,
                    "note": "Assessment not provided by caller",
                }

        readiness = {
            "dimensions": [d for d in dims if isinstance(d, str)],
            "results": results,
            "complete": (
                bool(dims)
                and all(
                    isinstance(results.get(d), dict)
                    and results[d].get("assessed") is True
                    for d in dims if isinstance(d, str)
                )
            ),
            "note": (
                "No readiness dimensions specified"
                if not dims else
                "All dimensions assessed"
                if all(
                    isinstance(results.get(d), dict)
                    and results[d].get("assessed") is True
                    for d in dims if isinstance(d, str)
                )
                else "Some dimensions not yet assessed"
            ),
        }

    # --- Source-change proposal (B: actionable with evidence) ---
    source_proposal = _build_source_proposal(
        doc_inputs, input_statuses, findings, ev_items,
    )

    # Original-snapshot fingerprint captures writer/source state at plan
    # time so that description/contributor edits between preview and
    # apply are detected as stale even when links and metadata are
    # unchanged.
    snapshot_fingerprint = _fingerprint({
        "key": issue_key,
        "description": validation.get(
            "sections", {}
        ),
        "contributors": sorted(contributors),
        "dependencies": sorted(dependencies),
    })

    plan = {
        "status": "complete",
        "issue_key": issue_key,
        "target": target,
        "inputs": input_statuses,
        "pr_links": pr_links,
        "metadata": metadata,
        "findings": findings,
        "source_proposal": source_proposal,
        "readiness": readiness,
        "snapshot_fingerprint": snapshot_fingerprint,
        "plan_digest": "",
    }
    plan["plan_digest"] = _fingerprint({
        "issue_key": issue_key,
        "target": target,
        "inputs": input_statuses,
        "pr_links": pr_links,
        "metadata": metadata,
        "snapshot_fingerprint": snapshot_fingerprint,
    })

    return plan


def _build_source_proposal(
    doc_inputs: list[dict[str, Any]],
    input_statuses: list[dict[str, Any]],
    findings: list[dict[str, str]],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an owning-source narrative-change proposal.

    Source/narrative apply is disabled.  The proposal carries:
    - Observations gathered per input with evidence refs
    - Input/source location references
    - Supporting PR/code evidence URLs
    - Intended owning-workflow action

    Observations are display-only context for human review — no
    automated semantic inference from free-form text.  Each
    observation is tied to its specific input and evidence source.
    """
    proposed_changes: list[dict[str, Any]] = []

    for inp_status in input_statuses:
        contrib = inp_status.get("contributor")
        text = inp_status.get("text", "")
        ev_refs = inp_status.get("evidence_refs", [])

        if not ev_refs:
            continue

        # Collect observations — display-only, no semantic inference
        observations: list[str] = []
        evidence_urls: list[str] = []

        for eref in ev_refs:
            evidence_urls.append(eref["pr_url"])
            observations.extend(eref.get("observations", []))

        # All observations are presented for human review — the skill
        # does not classify them as confirming or divergent
        if observations:
            proposed_changes.append({
                "action": "review",
                "contributor": contrib,
                "input_text": text,
                "proposed_wording": None,
                "reason": (
                    "Implementation observations require human review"
                ),
                "observations": observations,
                "evidence_urls": evidence_urls,
                "source_location": "Documentation Inputs",
            })

    # Non-contributor evidence: proposals with evidence URLs (B)
    for finding in findings:
        if finding.get("type") == "non_contributor_evidence":
            pr_url = finding.get("pr_url", "")
            proposed_changes.append({
                "action": "add_contributor",
                "contributor": finding["ref"],
                "input_text": "",
                "proposed_wording": (
                    f"Evaluate whether {finding['ref']} should be "
                    f"added as a contributor — PR evidence exists at "
                    f"{pr_url}"
                ),
                "reason": finding["detail"],
                "observations": [],
                "evidence_urls": [pr_url] if pr_url else [],
                "source_location": "Contributing stories + Documentation Inputs",
            })

    return {
        "apply_enabled": False,
        "reason": (
            "Source/narrative apply is disabled. No supported "
            "source-preserving handoff path is established for this "
            "invocation. Proposed changes should be reviewed and "
            "applied through the owning design workflow's /revise phase."
        ),
        "owning_workflow": "design",
        "owning_action": "/revise",
        "proposed_changes": proposed_changes,
    }


# ---------------------------------------------------------------------------
# Enrichment check  (D)
# ---------------------------------------------------------------------------


def check_enrichment(
    plan: dict[str, Any],
    current_state: dict[str, Any],
    approved_baseline: str = "",
    approved_plan_digest: str = "",
) -> dict[str, Any]:
    """Check proposed enrichment against current issue state.

    Args:
        plan: output of ``build_change_plan``
        current_state: current issue snapshot with ``key``,
            ``remote_links`` and optionally ``fields``
        approved_baseline: fingerprint from a previously approved
            preview — if provided and differs from the current
            baseline, the plan is stale
        approved_plan_digest: digest from a previously approved plan
            — if provided and differs from the current plan's digest,
            the plan has changed since approval

    Returns an enrichment result with eligibility, staleness, and
    detailed operation plan.
    """
    _empty_result: dict[str, Any] = {
        "eligible_links": [],
        "existing_links": [],
        "skipped_links": [],
        "eligible_metadata": {},
        "forbidden_fields": [],
        "plan_digest": plan.get("plan_digest", ""),
        "baseline_fingerprint": "",
        "stale": True,
    }

    # Reject invalid/blocked plans entirely (D)
    plan_status = plan.get("status", "")
    if plan_status != "complete":
        return {
            **_empty_result,
            "status": "invalid_plan",
            "reason": (
                f"plan status is '{plan_status}', not 'complete'"
            ),
        }

    # Require both identity keys (missing = invalid, not pass)
    plan_key = plan.get("issue_key", "")
    current_key = current_state.get("key", "")

    if not plan_key:
        return {
            **_empty_result,
            "status": "invalid_plan",
            "reason": "plan missing issue key",
        }

    if not current_key:
        return {
            **_empty_result,
            "status": "invalid",
            "reason": "current state missing issue key",
        }

    if current_key != plan_key:
        return {
            **_empty_result,
            "status": "wrong_issue",
            "reason": (
                f"plan targets {plan_key} but current state is "
                f"for {current_key}"
            ),
        }

    # Verify plan digest integrity (detect tampering)
    recomputed_digest = _fingerprint({
        "issue_key": plan.get("issue_key"),
        "target": plan.get("target"),
        "inputs": plan.get("inputs"),
        "pr_links": plan.get("pr_links"),
        "metadata": plan.get("metadata"),
        "snapshot_fingerprint": plan.get("snapshot_fingerprint", ""),
    })
    plan_digest = plan.get("plan_digest", "")

    # Empty plan_digest is invalid — a real plan always has one
    if not plan_digest:
        return {
            **_empty_result,
            "status": "invalid_plan",
            "reason": "plan has no digest",
        }

    if recomputed_digest != plan_digest:
        return {
            **_empty_result,
            "status": "invalid_plan",
            "reason": (
                "plan digest mismatch — plan may have been altered"
            ),
        }

    # Check approved plan digest (plan changed since approval)
    if approved_plan_digest and plan_digest != approved_plan_digest:
        return {
            **_empty_result,
            "status": "stale",
            "reason": "plan has changed since approval",
        }

    existing_links = current_state.get("remote_links", [])
    if not isinstance(existing_links, list):
        existing_links = []

    # Canonical link set for comparison (sorted for stable fingerprint)
    existing_urls: set[str] = set()
    canonical_links: list[dict[str, str]] = []
    for link in existing_links:
        url = link.get("url", "")
        try:
            norm = validate_pr_url(url, "existing_link")
        except ValueError:
            norm = url
        existing_urls.add(norm)
        canonical_links.append({"url": norm})
    canonical_links.sort(key=lambda x: x["url"])

    # Current metadata state for baseline
    current_fields = current_state.get("fields", {})
    current_metadata: dict[str, Any] = {}
    if isinstance(current_fields, dict):
        for fname, cat in _METADATA_CATALOG_V1.items():
            jf = cat["jira_field"]
            if jf in current_fields:
                # Normalize for stable fingerprint (sort by id)
                val = current_fields[jf]
                if isinstance(val, list):
                    val = sorted(
                        val,
                        key=lambda x: (
                            x.get("id", "") if isinstance(x, dict)
                            else str(x)
                        ),
                    )
                current_metadata[fname] = val

    # Baseline fingerprint from current state (links + metadata)
    baseline_fp = _fingerprint({
        "remote_links": canonical_links,
        "metadata": current_metadata,
    })

    # Staleness detection (D)
    stale = False
    if approved_baseline and approved_baseline != baseline_fp:
        stale = True

    # Writer/source drift: compare fresh snapshot against plan original
    plan_snapshot_fp = plan.get("snapshot_fingerprint", "")
    if plan_snapshot_fp:
        current_description = current_state.get("description")
        if current_description is None or not isinstance(
            current_description, str
        ):
            # Fail closed: cannot verify source state without description
            stale = True
        else:
            current_sections = _extract_sections(current_description)
            current_contribs = sorted(
                _extract_contributing_stories(current_description)
            )
            current_deps = sorted(
                _extract_dependencies(current_description)
            )
            fresh_fp = _fingerprint({
                "key": current_key,
                "description": current_sections,
                "contributors": current_contribs,
                "dependencies": current_deps,
            })
            if fresh_fp != plan_snapshot_fp:
                stale = True

    # Link eligibility
    eligible: list[dict[str, Any]] = []
    existing: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for proposed in plan.get("pr_links", []):
        url = proposed.get("url", "")
        try:
            norm_url = validate_pr_url(url, "proposed_link")
        except ValueError:
            skipped.append({**proposed, "reason": f"invalid URL: {url}"})
            continue
        if norm_url in existing_urls:
            existing.append({**proposed, "url": norm_url})
        else:
            eligible.append({**proposed, "url": norm_url})

    # Metadata eligibility (D: catalog_verified + validated catalog_entry)
    eligible_metadata: dict[str, Any] = {}
    forbidden_found: list[str] = []

    for field, spec in plan.get("metadata", {}).items():
        if field in _FORBIDDEN_FIELDS:
            forbidden_found.append(field)
            continue
        if field not in _ALLOWED_METADATA:
            forbidden_found.append(f"uncatalogued:{field}")
            continue
        if not isinstance(spec, dict):
            continue
        if not spec.get("catalog_verified", False):
            continue
        entry = spec.get("catalog_entry")
        if not isinstance(entry, dict):
            continue
        cat = _METADATA_CATALOG_V1.get(field, {})
        schema = cat.get("jira_item_schema", {})
        id_key = schema.get("id_field", "id")
        name_key = schema.get("name_field", "name")
        # Validate catalog_entry has non-empty id and name
        if not entry.get(id_key) or not entry.get(name_key):
            continue
        # Name must match requested value
        if entry.get(name_key) != spec.get("value"):
            continue
        # Build additive payload from actual current field state
        jira_fld = cat["jira_field"]
        before = (
            current_fields.get(jira_fld, [])
            if isinstance(current_fields, dict) else []
        )
        if not isinstance(before, list):
            before = []
        # Check if already present — no-op if so
        already = any(
            isinstance(b, dict) and b.get(id_key) == entry[id_key]
            for b in before
        )
        if already:
            payload = [
                {id_key: b.get(id_key)}
                for b in before if isinstance(b, dict)
            ]
        else:
            payload = [
                {id_key: b.get(id_key)}
                for b in before if isinstance(b, dict)
            ] + [{id_key: entry[id_key]}]
        expected_ids = sorted(
            {b.get(id_key) for b in before if isinstance(b, dict)}
            | {entry[id_key]}
        )
        eligible_metadata[field] = {
            **spec,
            "jira_payload": {cat["jira_field"]: payload},
            "expected_ids": expected_ids,
            "already_present": already,
        }

    # Profile forbidden fields
    profile_fields = current_state.get("profile_fields", {})
    if isinstance(profile_fields, dict):
        for pf in profile_fields:
            if pf in _FORBIDDEN_FIELDS:
                forbidden_found.append(f"profile:{pf}")

    return {
        "status": "stale" if stale else "ready",
        "eligible_links": [] if stale else eligible,
        "existing_links": existing,
        "skipped_links": skipped,
        "eligible_metadata": {} if stale else eligible_metadata,
        "forbidden_fields": forbidden_found,
        "plan_digest": plan.get("plan_digest", ""),
        "baseline_fingerprint": baseline_fp,
        "stale": stale,
    }


def verify_enrichment(
    enrichment: dict[str, Any],
    readback: dict[str, Any],
    expected_key: str = "",
) -> dict[str, Any]:
    """Verify enrichment results against a readback snapshot.

    Args:
        enrichment: output of ``check_enrichment``
        readback: fresh issue snapshot after writes (must include
            ``key`` and ``remote_links``)
        expected_key: if provided, verify the readback is for the
            correct issue

    Returns a receipt with per-operation status.
    """
    # Identity check (D) — missing key is invalid, not a pass
    readback_key = readback.get("key", "")
    if not readback_key:
        return {
            "status": "invalid",
            "reason": "readback missing issue key",
            "link_receipts": [],
            "metadata_receipts": [],
            "baseline_fingerprint": "",
            "all_confirmed": False,
        }
    if expected_key and readback_key != expected_key:
        return {
            "status": "wrong_issue",
            "reason": (
                f"expected readback for {expected_key} but got "
                f"{readback_key}"
            ),
            "link_receipts": [],
            "metadata_receipts": [],
            "baseline_fingerprint": "",
            "all_confirmed": False,
        }

    # Reject receipts for invalid/stale enrichments
    e_status = enrichment.get("status", "")
    if e_status not in ("ready",):
        return {
            "status": "invalid_enrichment",
            "reason": f"enrichment status is '{e_status}', not 'ready'",
            "link_receipts": [],
            "metadata_receipts": [],
            "baseline_fingerprint": "",
            "all_confirmed": False,
        }

    readback_links = readback.get("remote_links", [])
    if not isinstance(readback_links, list):
        readback_links = []

    readback_urls: set[str] = set()
    for link in readback_links:
        url = link.get("url", "")
        try:
            readback_urls.add(validate_pr_url(url, "readback"))
        except ValueError:
            readback_urls.add(url)

    # Link receipts
    link_receipts: list[dict[str, Any]] = []
    eligible_links = enrichment.get("eligible_links", [])
    existing_links = enrichment.get("existing_links", [])

    for link in eligible_links:
        url = link.get("url", "")
        try:
            norm = validate_pr_url(url, "receipt")
        except ValueError:
            norm = url
        found = norm in readback_urls
        link_receipts.append({
            "url": norm,
            "operation": "add",
            "applied": found,
            "status": "confirmed" if found else "uncertain",
        })

    for link in existing_links:
        url = link.get("url", "")
        try:
            norm = validate_pr_url(url, "receipt")
        except ValueError:
            norm = url
        found = norm in readback_urls
        link_receipts.append({
            "url": norm,
            "operation": "existing",
            "applied": found,
            "status": "confirmed" if found else "disappeared",
        })

    # Metadata receipts — use real Jira field binding from catalog
    metadata_receipts: list[dict[str, Any]] = []
    for field, spec in enrichment.get("eligible_metadata", {}).items():
        cat = _METADATA_CATALOG_V1.get(field, {})
        jira_field = cat.get("jira_field", field)
        readback_fields = readback.get("fields", {})
        if not isinstance(readback_fields, dict):
            readback_fields = {}
        current_val = readback_fields.get(jira_field)
        expected_entry = (
            spec.get("catalog_entry")
            if isinstance(spec, dict) else None
        )

        # For array fields (fixVersions), confirm FULL expected set
        expected_ids = (
            spec.get("expected_ids", [])
            if isinstance(spec, dict) else []
        )
        if (
            cat.get("jira_field_type") == "array"
            and isinstance(current_val, list)
            and expected_ids
        ):
            schema = cat.get("jira_item_schema", {})
            id_field = schema.get("id_field", "id")
            actual_ids = {
                item.get(id_field)
                for item in current_val
                if isinstance(item, dict)
            }
            all_present = all(
                eid in actual_ids for eid in expected_ids
            )
            status = "confirmed" if all_present else "partial"
        elif (
            cat.get("jira_field_type") == "array"
            and isinstance(expected_entry, dict)
            and isinstance(current_val, list)
        ):
            schema = cat.get("jira_item_schema", {})
            id_field = schema.get("id_field", "id")
            expected_id = expected_entry.get(id_field)
            found = any(
                isinstance(item, dict)
                and item.get(id_field) == expected_id
                for item in current_val
            ) if expected_id else False
            status = "confirmed" if found else "uncertain"
        elif current_val is not None and expected_entry is not None:
            status = (
                "confirmed" if current_val == expected_entry
                else "different_value"
            )
        elif expected_entry is not None:
            status = "uncertain"
        else:
            status = "uncertain"

        metadata_receipts.append({
            "field": field,
            "jira_field": jira_field,
            "status": status,
            "expected": expected_entry,
            "expected_ids": expected_ids,
            "actual": current_val,
        })

    # New baseline — includes metadata state (matches check_enrichment)
    canonical: list[dict[str, str]] = []
    for link in readback_links:
        url = link.get("url", "")
        try:
            canonical.append({"url": validate_pr_url(url, "_")})
        except ValueError:
            canonical.append({"url": url})
    canonical.sort(key=lambda x: x["url"])

    rb_fields = readback.get("fields", {})
    rb_metadata: dict[str, Any] = {}
    if isinstance(rb_fields, dict):
        for fname, cat in _METADATA_CATALOG_V1.items():
            jf = cat["jira_field"]
            if jf in rb_fields:
                val = rb_fields[jf]
                if isinstance(val, list):
                    val = sorted(
                        val,
                        key=lambda x: (
                            x.get("id", "")
                            if isinstance(x, dict) else str(x)
                        ),
                    )
                rb_metadata[fname] = val

    new_baseline = _fingerprint({
        "remote_links": canonical,
        "metadata": rb_metadata,
    })

    # All confirmed: must have at least one operation, and all must
    # be confirmed (empty eligible = no-op, not success)
    all_ops = link_receipts + metadata_receipts
    add_ops = [
        r for r in all_ops
        if r.get("operation") != "existing"
    ]
    all_confirmed = (
        bool(add_ops)
        and all(r.get("status") == "confirmed" for r in add_ops)
    )

    return {
        "status": "verified",
        "link_receipts": link_receipts,
        "metadata_receipts": metadata_receipts,
        "baseline_fingerprint": new_baseline,
        "all_confirmed": all_confirmed,
    }


# ---------------------------------------------------------------------------
# Handoff rendering
# ---------------------------------------------------------------------------


def render_handoff(plan: dict[str, Any]) -> str:
    """Render a human-readable handoff document from a change plan."""
    parts: list[str] = []
    issue_key = plan.get("issue_key", "unknown")
    target = plan.get("target", {})

    parts.append(f"# Documentation Handoff — {issue_key}")
    parts.append("")
    parts.append(
        f"**Target release:** {target.get('release', 'not specified')}"
    )
    parts.append(
        f"**Target branch:** {target.get('target_branch', 'not specified')}"
    )
    parts.append("")

    inputs = plan.get("inputs", [])
    status_counts: dict[str, int] = {}
    for i in inputs:
        s = i.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    parts.append("## Delivery Summary")
    parts.append("")
    for status_name in sorted(status_counts):
        parts.append(f"- {status_name}: {status_counts[status_name]}")
    parts.append(f"- Total inputs: {len(inputs)}")
    parts.append("")

    if inputs:
        parts.append("## Input Status")
        parts.append("")
        parts.append("| Input | Contributor | Status | Evidence |")
        parts.append("|---|---|---|---|")
        for inp in inputs:
            text = inp.get("text", "")[:60]
            contrib = inp.get("contributor", "")
            status = inp.get("status", "unknown")
            ev_refs = inp.get("evidence_refs", [])
            ev_summary = ", ".join(
                f"{r['pr_url']} ({r['pr_status']})" for r in ev_refs
            ) if ev_refs else "none"
            parts.append(
                f"| {text} | {contrib} | {status} | {ev_summary} |"
            )
        parts.append("")

    target_notes = [
        n for inp in inputs for n in inp.get("target_notes", [])
    ]
    if target_notes:
        parts.append("## Target Branch Notes")
        parts.append("")
        for note in target_notes:
            parts.append(f"- {note}")
        parts.append("")

    findings = plan.get("findings", [])
    if findings:
        parts.append("## Findings")
        parts.append("")
        for f in findings:
            parts.append(
                f"- **{f['type']}** ({f.get('ref', '')}): "
                f"{f.get('detail', '')}"
            )
            if f.get("pr_url"):
                parts.append(f"  Evidence: {f['pr_url']}")
        parts.append("")

    pr_links = plan.get("pr_links", [])
    if pr_links:
        parts.append("## PR Remote Links (contributor PRs only)")
        parts.append("")
        parts.append("| URL | Title | Contributors |")
        parts.append("|---|---|---|")
        for link in pr_links:
            url = link.get("url", "")
            title = link.get("title", "")
            contribs = ", ".join(link.get("contributor_keys", []))
            parts.append(f"| {url} | {title} | {contribs} |")
        parts.append("")

    metadata = plan.get("metadata", {})
    if metadata:
        parts.append("## Metadata Proposals")
        parts.append("")
        for field, spec in metadata.items():
            if isinstance(spec, dict):
                val = spec.get("value", "")
                verified = spec.get("catalog_verified", False)
                parts.append(
                    f"- **{field}**: {val} "
                    f"(catalog verified: {verified})"
                )
            else:
                parts.append(f"- **{field}**: {spec}")
        parts.append("")

    source = plan.get("source_proposal")
    if source:
        parts.append("## Source Change Proposal")
        parts.append("")
        parts.append(
            f"**Apply enabled:** {source.get('apply_enabled', False)}"
        )
        parts.append(f"**Reason:** {source.get('reason', '')}")
        changes = source.get("proposed_changes", [])
        if changes:
            parts.append("")
            parts.append(
                f"**Owning workflow:** "
                f"{source.get('owning_workflow', '')}"
            )
            parts.append(
                f"**Owning action:** {source.get('owning_action', '')}"
            )
            parts.append("")
            for change in changes:
                action = change.get("action", "")
                contrib = change.get("contributor", "")
                wording = change.get("proposed_wording", "")
                ev_urls = change.get("evidence_urls", [])
                parts.append(f"### {action}: {contrib}")
                parts.append("")
                if wording:
                    parts.append(f"**Proposed:** {wording}")
                if change.get("input_text"):
                    parts.append(
                        f"**Current input:** {change['input_text']}"
                    )
                if ev_urls:
                    parts.append(
                        f"**Evidence:** {', '.join(ev_urls)}"
                    )
                parts.append("")
        parts.append("")

    readiness = plan.get("readiness")
    if readiness:
        parts.append("## Consumer Readiness")
        parts.append("")
        dims = readiness.get("dimensions", [])
        if dims:
            parts.append(f"**Dimensions:** {', '.join(dims)}")
        else:
            parts.append("**Dimensions:** none specified")
        parts.append(
            f"**Complete:** {readiness.get('complete', False)}"
        )
        results = readiness.get("results", {})
        if results:
            for dim, res in results.items():
                if isinstance(res, dict):
                    assessed = res.get("assessed", False)
                    note = res.get("note", "")
                    parts.append(f"- {dim}: assessed={assessed} {note}")
                else:
                    parts.append(f"- {dim}: {res}")
        parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Run the validate subcommand."""
    snapshot = _load_json(args.input)
    if not isinstance(snapshot, dict):
        fail("input must be a JSON object")

    original = copy.deepcopy(snapshot)
    result = validate_issue(snapshot)
    if snapshot != original:
        fail("BUG: validate_issue mutated its input")

    _write_json(result)
    return EXIT_SUCCESS if result["valid"] else EXIT_ERROR


def cmd_normalize(args: argparse.Namespace) -> int:
    """Run the normalize subcommand."""
    data = _load_json(args.input)
    if not isinstance(data, list):
        fail("input must be a JSON array of evidence items")

    original = copy.deepcopy(data)
    result = normalize_evidence(data)
    if data != original:
        fail("BUG: normalize_evidence mutated its input")

    _write_json(result)
    return EXIT_SUCCESS if not result["errors"] else EXIT_ERROR


def cmd_build_plan(args: argparse.Namespace) -> int:
    """Run the build-plan subcommand."""
    data = _load_json(args.input)
    if not isinstance(data, dict):
        fail("input must be a JSON object")

    validation = data.get("validation")
    evidence_raw = data.get("evidence")
    target = data.get("target", {})
    profile = data.get("profile")

    if not isinstance(validation, dict):
        fail("input.validation must be an object")
    if not isinstance(evidence_raw, dict):
        fail("input.evidence must be an object")
    if not isinstance(target, dict):
        fail("input.target must be an object")

    original = copy.deepcopy(data)
    plan = build_change_plan(validation, evidence_raw, target, profile)
    if data != original:
        fail("BUG: build_change_plan mutated its input")

    _write_json(plan)
    # Invalid issue/evidence → exit 1
    if plan["status"] != "complete":
        return EXIT_ERROR
    return EXIT_SUCCESS


def cmd_check_enrichment(args: argparse.Namespace) -> int:
    """Run the check-enrichment subcommand."""
    data = _load_json(args.input)
    if not isinstance(data, dict):
        fail("input must be a JSON object")

    plan = data.get("plan")
    current = data.get("current_state")
    approved_baseline = data.get("approved_baseline", "")

    if not isinstance(plan, dict):
        fail("input.plan must be an object")
    if not isinstance(current, dict):
        fail("input.current_state must be an object")

    approved_plan_digest = data.get("approved_plan_digest", "")

    if args.readback:
        readback = _load_json(Path(args.readback))
        if not isinstance(readback, dict):
            fail("readback must be a JSON object")
        enrichment = check_enrichment(
            plan, current, approved_baseline, approved_plan_digest,
        )
        expected_key = plan.get("issue_key", "")
        receipt = verify_enrichment(enrichment, readback, expected_key)
        _write_json({"enrichment": enrichment, "receipt": receipt})
        if receipt.get("status") != "verified":
            return EXIT_ERROR
    else:
        original = copy.deepcopy(data)
        result = check_enrichment(
            plan, current, approved_baseline, approved_plan_digest,
        )
        if data != original:
            fail("BUG: check_enrichment mutated its input")
        _write_json(result)
        if result.get("stale") or result.get("status") != "ready":
            return EXIT_ERROR

    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Entry point for the evidence CLI."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    p_validate = sub.add_parser(
        "validate",
        help="Validate a DOCS issue snapshot and extract contributors",
    )
    p_validate.add_argument("--input", required=True, type=Path)

    p_normalize = sub.add_parser(
        "normalize",
        help="Normalize and deduplicate raw PR evidence items",
    )
    p_normalize.add_argument("--input", required=True, type=Path)

    p_plan = sub.add_parser(
        "build-plan",
        help="Build a delivery-evidence change plan",
    )
    p_plan.add_argument("--input", required=True, type=Path)

    p_enrich = sub.add_parser(
        "check-enrichment",
        help="Check proposed enrichment against current state",
    )
    p_enrich.add_argument("--input", required=True, type=Path)
    p_enrich.add_argument("--readback", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args)
    elif args.command == "normalize":
        return cmd_normalize(args)
    elif args.command == "build-plan":
        return cmd_build_plan(args)
    elif args.command == "check-enrichment":
        return cmd_check_enrichment(args)
    else:
        fail(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
