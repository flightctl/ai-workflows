#!/usr/bin/env python3
"""Deterministic delivery-evidence operations for the docs-handoff skill.

Provides subcommands for validating DOCS issue structure, extracting
contributor references, normalizing PR evidence, building bounded
change plans, and checking enrichment idempotency.

Subcommands:
  validate         Validate a DOCS issue snapshot and extract contributors
  build-plan       Build a delivery-evidence change plan from gathered evidence
  check-enrichment Check proposed enrichment against existing issue state

All inputs come from files or stdin (JSON).  This script never contacts
Jira, GitHub, or any external service.  ``urllib.parse`` is used for
URL validation only -- no network I/O.

Exit codes:
  0 -- success (result JSON on stdout)
  1 -- input validation error or data inconsistency (diagnostic on stderr)
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
# URL validation
# ---------------------------------------------------------------------------

# Allowed PR URL host patterns (public forges)
_PR_URL_RE = re.compile(
    r"^https://(?:github\.com|gitlab\.com|gitlab\.[a-z0-9.-]+)"
    r"/[^/]+/[^/]+/(?:pull|merge_requests)/\d+/?$"
)


def validate_url(url: str, label: str = "url") -> str:
    """Validate an HTTP(S) URL without embedded credentials.

    Returns the normalized URL (trailing slash stripped) or raises
    ValueError with a descriptive message.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{label}: must be a non-empty string")
    url = url.strip()

    # Reject control characters and whitespace
    if any(ord(c) < 32 or c.isspace() for c in url):
        raise ValueError(f"{label}: contains whitespace or control characters")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"{label}: must use http or https scheme")
    if not parsed.hostname:
        raise ValueError(f"{label}: missing hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{label}: must not contain embedded credentials")

    # Strip trailing slash for normalization
    normalized = url.rstrip("/")
    return normalized


def validate_pr_url(url: str, label: str = "pr_url") -> str:
    """Validate and normalize a pull/merge request URL.

    Returns the normalized URL or raises ValueError.
    """
    normalized = validate_url(url, label)
    # Strip fragment and query for identity comparison
    parsed = urlsplit(normalized)
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    clean = clean.rstrip("/")
    return clean


def extract_pr_identity(url: str) -> dict[str, str]:
    """Extract owner, repo, and PR number from a normalized PR URL.

    Returns a dict with ``owner``, ``repo``, ``number``, ``host``.
    Raises ValueError if the URL is not a recognized PR URL.
    """
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    # GitHub: owner/repo/pull/N  GitLab: owner/repo/-/merge_requests/N
    if len(parts) >= 4 and parts[2] == "pull":
        return {
            "host": parsed.hostname or "",
            "owner": parts[0],
            "repo": parts[1],
            "number": parts[3],
        }
    # GitLab with /-/ prefix
    if len(parts) >= 5 and parts[2] == "-" and parts[3] == "merge_requests":
        return {
            "host": parsed.hostname or "",
            "owner": parts[0],
            "repo": parts[1],
            "number": parts[4],
        }
    # GitLab without /-/ prefix
    if len(parts) >= 4 and parts[2] == "merge_requests":
        return {
            "host": parsed.hostname or "",
            "owner": parts[0],
            "repo": parts[1],
            "number": parts[3],
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
# DOCS issue validation and contributor extraction
# ---------------------------------------------------------------------------

# Sections expected in a rendered DOCS issue description
_DOCS_SECTIONS = {
    "Documentation Inputs",
    "Documentation Scope",
    "Acceptance Criteria",
}


def _extract_sections(text: str) -> dict[str, str]:
    """Extract ## sections from rendered Jira markdown description.

    Returns heading -> body text mapping.
    """
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
    """Extract Contributing stories references from a rendered description.

    Looks for a ``Contributing stories:`` line in the Design Reference
    section or in the full description.  Returns a list of Jira keys
    found on that line.  Local ``Story N.NN`` placeholders without Jira
    keys are returned as qualified IDs (``story-N.NN``) and flagged as
    unresolved.
    """
    result: list[str] = []
    seen: set[str] = set()
    for line in description.splitlines():
        stripped = line.strip()
        # Normalize list-item prefixes
        for pfx in ("- ", "* ", "+ "):
            if stripped.startswith(pfx):
                stripped = stripped[len(pfx):].strip()
                break
        if not stripped.lower().startswith("contributing stories:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        # Extract Jira keys (rendered form)
        for key in extract_all_jira_keys(value):
            if key not in seen:
                seen.add(key)
                result.append(key)
        # Extract unresolved Story N.NN placeholders
        for qid in extract_story_refs(value):
            if qid not in seen:
                seen.add(qid)
                result.append(qid)
    return result


def _extract_dependencies(description: str) -> list[str]:
    """Extract Dependencies references from a rendered description.

    Returns Jira keys and unresolved story refs found in the Dependencies
    section only.
    """
    sections = _extract_sections(description)
    deps_text = sections.get("Dependencies", "")
    if not deps_text:
        # Try inline Dependencies: line
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

    Recognizes bold contributor headers (``**Story N.NN -- title:**`` or
    ``**JIRA-KEY -- title:**``) followed by bullet-pointed input items.
    Each input may have ``[Assumption]`` or ``[Open: ...]`` markers.
    """
    items: list[dict[str, Any]] = []
    current_contributor: str | None = None
    contributor_key: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        # Bold contributor header: **KEY -- title:** or **Story N.NN -- title:**
        header_match = re.match(
            r"\*\*(.+?)(?:\s*(?:--|—)\s*.+?)?\s*:?\*\*:?\s*$",
            stripped,
        )
        if header_match:
            header_text = header_match.group(1).strip()
            # Extract key from header
            key = parse_jira_key(header_text)
            if key:
                contributor_key = key
                current_contributor = header_text
            else:
                # May be Story N.NN format
                refs = extract_story_refs(header_text)
                if refs:
                    contributor_key = refs[0]
                    current_contributor = header_text
                else:
                    contributor_key = header_text
                    current_contributor = header_text
            continue

        # Bullet item under a contributor
        bullet_match = re.match(r"[-*+]\s+(.*)", stripped)
        if bullet_match and current_contributor is not None:
            item_text = bullet_match.group(1).strip()
            marker = "planned"
            open_ref = None
            if "[Assumption]" in item_text:
                marker = "assumption"
                item_text = item_text.replace("[Assumption]", "").strip()
            open_match = re.search(r"\[Open:\s*([^\]]+)\]", item_text)
            if open_match:
                marker = "open"
                open_ref = open_match.group(1).strip()
                item_text = re.sub(r"\[Open:\s*[^\]]+\]", "", item_text).strip()

            items.append({
                "contributor": contributor_key,
                "contributor_header": current_contributor,
                "text": item_text,
                "marker": marker,
                "open_ref": open_ref,
            })

    return items


def validate_issue(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate a DOCS issue snapshot and extract structured data.

    Input: a JSON object with at minimum ``key``, ``summary``,
    ``description``.  May include ``status``, ``parent``,
    ``remote_links``, ``issue_links``.

    Returns a result object with ``valid``, ``errors``, ``warnings``,
    and extracted ``contributors``, ``dependencies``,
    ``documentation_inputs``, ``sections``.
    """
    errors: list[str] = []
    warnings: list[str] = []

    key = snapshot.get("key")
    if not key or not isinstance(key, str):
        errors.append("missing or invalid 'key' field")
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

    # Check required sections
    missing_sections = _DOCS_SECTIONS - set(sections.keys())
    for ms in sorted(missing_sections):
        errors.append(f"missing required section: {ms}")

    # Extract contributors
    contributors = _extract_contributing_stories(description)
    unresolved = [c for c in contributors if c.startswith("story-")]
    if unresolved:
        for u in unresolved:
            warnings.append(f"unresolved local reference: {u}")

    if not contributors:
        errors.append("no Contributing stories found in description")

    # Extract dependencies (distinct from contributors)
    dependencies = _extract_dependencies(description)

    # Parse documentation inputs
    doc_inputs_text = sections.get("Documentation Inputs", "")
    documentation_inputs = _parse_documentation_inputs(doc_inputs_text)
    if not documentation_inputs and "Documentation Inputs" in sections:
        warnings.append(
            "Documentation Inputs section exists but no structured items parsed"
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
# Evidence normalization
# ---------------------------------------------------------------------------


def normalize_evidence(
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalize and deduplicate gathered PR evidence.

    Each evidence item must have ``pr_url``, ``contributor_key``, and
    optionally ``target_branch``, ``state``, ``title``, ``merged``,
    ``merge_commit``, ``observations`` (list of strings from AI review).

    Returns ``{"items": [...], "errors": [...], "warnings": [...]}``.
    Deduplication is by normalized PR URL.
    """
    errors: list[str] = []
    warnings: list[str] = []
    seen_urls: dict[str, int] = {}
    normalized: list[dict[str, Any]] = []

    if not isinstance(evidence_items, list):
        return {"items": [], "errors": ["evidence must be an array"], "warnings": []}

    for i, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            errors.append(f"evidence[{i}]: must be an object")
            continue

        pr_url_raw = item.get("pr_url", "")
        contributor = item.get("contributor_key", "")

        if not contributor or not isinstance(contributor, str):
            errors.append(f"evidence[{i}]: missing contributor_key")
            continue

        try:
            pr_url = validate_pr_url(pr_url_raw, f"evidence[{i}].pr_url")
        except ValueError as exc:
            errors.append(str(exc))
            continue

        # Deduplicate by normalized URL
        if pr_url in seen_urls:
            existing_idx = seen_urls[pr_url]
            # Merge contributor if different
            existing = normalized[existing_idx]
            if contributor not in existing.get("contributor_keys", []):
                existing.setdefault("contributor_keys", [contributor])
                if contributor not in existing["contributor_keys"]:
                    existing["contributor_keys"].append(contributor)
            warnings.append(
                f"evidence[{i}]: duplicate PR URL {pr_url} "
                f"(merged with evidence[{existing_idx}])"
            )
            continue

        # Extract PR identity
        try:
            pr_id = extract_pr_identity(pr_url)
        except ValueError:
            pr_id = {}

        entry: dict[str, Any] = {
            "pr_url": pr_url,
            "contributor_keys": [contributor],
            "pr_identity": pr_id,
            "target_branch": item.get("target_branch", ""),
            "state": item.get("state", ""),
            "title": item.get("title", ""),
            "merged": item.get("merged"),
            "merge_commit": item.get("merge_commit", ""),
            "observations": item.get("observations", []),
        }

        seen_urls[pr_url] = len(normalized)
        normalized.append(entry)

    return {"items": normalized, "errors": errors, "warnings": warnings}


# ---------------------------------------------------------------------------
# Change plan
# ---------------------------------------------------------------------------


def _fingerprint(data: Any) -> str:
    """Compute a stable SHA-256 fingerprint of JSON-serializable data."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def build_change_plan(
    validation: dict[str, Any],
    evidence: dict[str, Any],
    target: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a delivery-evidence change plan.

    Args:
        validation: output of ``validate_issue``
        evidence: output of ``normalize_evidence``
        target: ``{"release": "...", "target_branch": "..."}``
        profile: optional caller-supplied consumer profile

    Returns a plan object with ``status``, ``inputs``, ``pr_links``,
    ``metadata``, ``findings``, ``source_proposal``, and ``fingerprint``.
    """
    errors: list[str] = []
    findings: list[dict[str, str]] = []

    if not validation.get("valid"):
        return {
            "status": "invalid_issue",
            "errors": validation.get("errors", []),
            "inputs": [],
            "pr_links": [],
            "metadata": {},
            "findings": findings,
            "source_proposal": None,
            "readiness": None,
            "fingerprint": "",
        }

    issue_key = validation["key"]
    contributors = set(validation.get("contributors", []))
    dependencies = set(validation.get("dependencies", []))
    doc_inputs = validation.get("documentation_inputs", [])
    evidence_items = evidence.get("items", [])
    target_release = target.get("release", "")
    target_branch = target.get("target_branch", "")

    # --- Per-input delivery status ---
    input_statuses: list[dict[str, Any]] = []
    contributor_evidence: dict[str, list[dict[str, Any]]] = {}

    for ev in evidence_items:
        for ck in ev.get("contributor_keys", []):
            contributor_evidence.setdefault(ck, []).append(ev)

    # Track which contributors had evidence
    contributors_with_evidence: set[str] = set()

    for doc_input in doc_inputs:
        contrib = doc_input.get("contributor")
        evs = contributor_evidence.get(contrib, [])

        status = "missing"
        pr_refs: list[str] = []
        target_notes: list[str] = []

        if evs:
            contributors_with_evidence.add(contrib)
            has_merged = any(e.get("merged") is True for e in evs)
            status = "delivered" if has_merged else "in_progress"
            pr_refs = [e["pr_url"] for e in evs]

            for ev in evs:
                ev_target = ev.get("target_branch", "")
                if target_branch and ev_target and ev_target != target_branch:
                    target_notes.append(
                        f"PR {ev['pr_url']} targets {ev_target}, "
                        f"expected {target_branch}"
                    )

        input_statuses.append({
            "text": doc_input.get("text", ""),
            "contributor": contrib,
            "marker": doc_input.get("marker", "planned"),
            "status": status,
            "pr_refs": pr_refs,
            "target_notes": target_notes,
        })

    # --- Contributors without evidence ---
    for contrib in sorted(contributors):
        if contrib not in contributors_with_evidence:
            if contrib.startswith("story-"):
                findings.append({
                    "type": "unresolved_contributor",
                    "ref": contrib,
                    "detail": (
                        f"Contributor {contrib} is an unresolved local "
                        f"reference with no Jira key mapping"
                    ),
                })
            elif contrib not in dependencies:
                findings.append({
                    "type": "missing_evidence",
                    "ref": contrib,
                    "detail": (
                        f"Contributing story {contrib} has no "
                        f"associated PR evidence"
                    ),
                })

    # --- Evidence for non-contributors (new surfaces) ---
    all_contributor_keys: set[str] = set()
    for di in doc_inputs:
        c = di.get("contributor")
        if c:
            all_contributor_keys.add(c)
    all_contributor_keys |= contributors

    for ev in evidence_items:
        for ck in ev.get("contributor_keys", []):
            if ck not in all_contributor_keys:
                findings.append({
                    "type": "new_surface",
                    "ref": ck,
                    "detail": (
                        f"PR {ev['pr_url']} is attributed to {ck} "
                        f"which is not a listed contributor"
                    ),
                })

    # --- PR Remote Links to add ---
    pr_links: list[dict[str, Any]] = []
    for ev in evidence_items:
        pr_links.append({
            "url": ev["pr_url"],
            "title": ev.get("title", ""),
            "relationship": "implements",
            "contributor_keys": ev.get("contributor_keys", []),
        })

    # --- Metadata proposals ---
    metadata: dict[str, Any] = {}
    if target_release:
        metadata["proposed_target_release"] = target_release

    # Profile-based readiness (independent of delivery)
    readiness: dict[str, Any] | None = None
    if profile:
        dims = profile.get("readiness_dimensions", [])
        if dims:
            readiness = {
                "dimensions": dims,
                "results": {},
                "complete": False,
                "note": (
                    "Consumer readiness assessment requires evaluating "
                    "each dimension against actual delivery evidence. "
                    "Dimensions are recorded; results must be populated "
                    "by the caller with actual assessments."
                ),
            }
        else:
            readiness = {
                "dimensions": [],
                "results": {},
                "complete": False,
                "note": "No readiness dimensions in consumer profile",
            }

    # --- Source-change proposal ---
    source_proposal = _build_source_proposal(
        doc_inputs, input_statuses, findings, evidence_items
    )

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
        "fingerprint": "",
    }
    plan["fingerprint"] = _fingerprint({
        "issue_key": issue_key,
        "inputs": input_statuses,
        "pr_links": pr_links,
        "metadata": metadata,
    })

    return plan


def _build_source_proposal(
    doc_inputs: list[dict[str, Any]],
    input_statuses: list[dict[str, Any]],
    findings: list[dict[str, str]],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an owning-source narrative-change proposal.

    This produces a structured proposal that the owning design workflow
    could apply via its ``/revise`` phase.  The proposal includes
    specific intended changes to the Documentation Inputs section with
    supporting evidence references.

    The docs-handoff skill does NOT directly apply these changes.
    Source/narrative apply is disabled; the proposal is advisory.
    """
    proposed_changes: list[dict[str, Any]] = []

    for inp_status in input_statuses:
        status = inp_status["status"]
        contrib = inp_status["contributor"]
        text = inp_status["text"]

        if status == "delivered":
            # Check if observations suggest the actual implementation
            # differs from the planned input
            relevant_evs = [
                e for e in evidence_items
                if contrib in e.get("contributor_keys", [])
            ]
            has_observations = any(
                e.get("observations") for e in relevant_evs
            )
            if has_observations:
                all_obs = []
                for e in relevant_evs:
                    all_obs.extend(e.get("observations", []))
                proposed_changes.append({
                    "action": "update",
                    "contributor": contrib,
                    "input_text": text,
                    "reason": "Implementation observations suggest differences",
                    "observations": all_obs,
                    "evidence_urls": [e["pr_url"] for e in relevant_evs],
                })

    # New surfaces from non-contributors
    for finding in findings:
        if finding["type"] == "new_surface":
            proposed_changes.append({
                "action": "add",
                "contributor": finding["ref"],
                "input_text": "",
                "reason": finding["detail"],
                "observations": [],
                "evidence_urls": [],
            })

    return {
        "apply_enabled": False,
        "reason": (
            "Source/narrative apply is disabled. No supported "
            "source-preserving handoff path is established for this "
            "invocation. Proposed changes should be reviewed and applied "
            "through the owning design workflow's /revise phase."
        ),
        "owning_workflow": "design",
        "owning_action": "/revise",
        "proposed_changes": proposed_changes,
    }


# ---------------------------------------------------------------------------
# Enrichment check
# ---------------------------------------------------------------------------


def check_enrichment(
    plan: dict[str, Any],
    current_state: dict[str, Any],
) -> dict[str, Any]:
    """Check proposed enrichment against current issue state.

    Args:
        plan: output of ``build_change_plan``
        current_state: current issue snapshot with ``remote_links``
            (list of ``{"url": ..., "title": ...}``) and
            optionally ``fields`` (dict of field names to values)

    Returns an enrichment result with ``eligible_links``,
    ``existing_links``, ``skipped_links``, ``eligible_metadata``,
    ``forbidden_fields``, ``plan_fingerprint``, ``baseline_fingerprint``,
    ``stale``.
    """
    # Forbidden fields that this skill must never modify
    FORBIDDEN = {
        "summary", "description", "status", "assignee",
        "sprint", "parent", "labels", "comment",
        "resolution", "priority", "issuetype",
    }

    existing_links = current_state.get("remote_links", [])
    existing_urls: set[str] = set()
    for link in existing_links:
        url = link.get("url", "")
        try:
            existing_urls.add(validate_pr_url(url, "existing_link"))
        except ValueError:
            existing_urls.add(url)

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

    # Metadata eligibility
    eligible_metadata: dict[str, Any] = {}
    forbidden_found: list[str] = []
    for field, value in plan.get("metadata", {}).items():
        base_field = field.replace("proposed_", "")
        if base_field in FORBIDDEN:
            forbidden_found.append(field)
        else:
            eligible_metadata[field] = value

    # Check profile-based field overrides
    profile_fields = current_state.get("profile_fields", {})
    for pf in profile_fields:
        if pf in FORBIDDEN:
            forbidden_found.append(f"profile:{pf}")

    # Baseline fingerprint for drift detection
    baseline_fp = _fingerprint({
        "remote_links": [
            {"url": l.get("url", "")} for l in existing_links
        ],
    })

    return {
        "eligible_links": eligible,
        "existing_links": existing,
        "skipped_links": skipped,
        "eligible_metadata": eligible_metadata,
        "forbidden_fields": forbidden_found,
        "plan_fingerprint": plan.get("fingerprint", ""),
        "baseline_fingerprint": baseline_fp,
        "stale": False,
    }


def verify_enrichment(
    expected: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    """Verify enrichment results against a readback snapshot.

    Args:
        expected: the enrichment result from ``check_enrichment``
        readback: fresh issue snapshot after writes

    Returns a receipt with per-operation status.
    """
    readback_links = readback.get("remote_links", [])
    readback_urls: set[str] = set()
    for link in readback_links:
        url = link.get("url", "")
        try:
            readback_urls.add(validate_pr_url(url, "readback"))
        except ValueError:
            readback_urls.add(url)

    receipts: list[dict[str, Any]] = []
    for link in expected.get("eligible_links", []):
        url = link.get("url", "")
        try:
            norm = validate_pr_url(url, "receipt")
        except ValueError:
            norm = url
        found = norm in readback_urls
        receipts.append({
            "url": norm,
            "applied": found,
            "status": "confirmed" if found else "uncertain",
        })

    # Baseline drift check
    new_baseline = _fingerprint({
        "remote_links": [
            {"url": l.get("url", "")} for l in readback_links
        ],
    })

    return {
        "receipts": receipts,
        "baseline_fingerprint": new_baseline,
        "all_confirmed": all(r["applied"] for r in receipts),
    }


# ---------------------------------------------------------------------------
# Handoff rendering
# ---------------------------------------------------------------------------


def render_handoff(plan: dict[str, Any]) -> str:
    """Render a human-readable handoff document from a change plan.

    Produces deterministic Markdown suitable for writer consumption.
    """
    parts: list[str] = []
    issue_key = plan.get("issue_key", "unknown")
    target = plan.get("target", {})

    parts.append(f"# Documentation Handoff — {issue_key}")
    parts.append("")
    parts.append(f"**Target release:** {target.get('release', 'not specified')}")
    parts.append(f"**Target branch:** {target.get('target_branch', 'not specified')}")
    parts.append("")

    # Delivery summary
    inputs = plan.get("inputs", [])
    delivered = sum(1 for i in inputs if i["status"] == "delivered")
    in_progress = sum(1 for i in inputs if i["status"] == "in_progress")
    missing = sum(1 for i in inputs if i["status"] == "missing")

    parts.append("## Delivery Summary")
    parts.append("")
    parts.append(f"- Delivered: {delivered}")
    parts.append(f"- In progress: {in_progress}")
    parts.append(f"- Missing evidence: {missing}")
    parts.append(f"- Total inputs: {len(inputs)}")
    parts.append("")

    # Per-input details
    if inputs:
        parts.append("## Input Status")
        parts.append("")
        parts.append("| Input | Contributor | Status | PRs |")
        parts.append("|---|---|---|---|")
        for inp in inputs:
            text = inp.get("text", "")[:60]
            contrib = inp.get("contributor", "")
            status = inp.get("status", "unknown")
            prs = ", ".join(inp.get("pr_refs", []))
            if not prs:
                prs = "none"
            parts.append(f"| {text} | {contrib} | {status} | {prs} |")
        parts.append("")

    # Target notes
    target_notes = [
        n for inp in inputs for n in inp.get("target_notes", [])
    ]
    if target_notes:
        parts.append("## Target Branch Notes")
        parts.append("")
        for note in target_notes:
            parts.append(f"- {note}")
        parts.append("")

    # Findings
    findings = plan.get("findings", [])
    if findings:
        parts.append("## Findings")
        parts.append("")
        for f in findings:
            parts.append(f"- **{f['type']}** ({f.get('ref', '')}): {f.get('detail', '')}")
        parts.append("")

    # PR links to add
    pr_links = plan.get("pr_links", [])
    if pr_links:
        parts.append("## PR Remote Links")
        parts.append("")
        parts.append("| URL | Relationship | Contributors |")
        parts.append("|---|---|---|")
        for link in pr_links:
            url = link.get("url", "")
            rel = link.get("relationship", "")
            contribs = ", ".join(link.get("contributor_keys", []))
            parts.append(f"| {url} | {rel} | {contribs} |")
        parts.append("")

    # Source proposal
    source = plan.get("source_proposal")
    if source:
        parts.append("## Source Change Proposal")
        parts.append("")
        parts.append(f"**Apply enabled:** {source.get('apply_enabled', False)}")
        parts.append(f"**Reason:** {source.get('reason', '')}")
        if source.get("proposed_changes"):
            parts.append("")
            parts.append(f"**Owning workflow:** {source.get('owning_workflow', '')}")
            parts.append(f"**Owning action:** {source.get('owning_action', '')}")
            parts.append("")
            for change in source["proposed_changes"]:
                action = change.get("action", "")
                contrib = change.get("contributor", "")
                reason = change.get("reason", "")
                parts.append(f"- **{action}** {contrib}: {reason}")
        parts.append("")

    # Readiness
    readiness = plan.get("readiness")
    if readiness:
        parts.append("## Consumer Readiness")
        parts.append("")
        dims = readiness.get("dimensions", [])
        if dims:
            parts.append(f"**Dimensions:** {', '.join(dims)}")
        else:
            parts.append("**Dimensions:** none specified")
        parts.append(f"**Complete:** {readiness.get('complete', False)}")
        parts.append(f"**Note:** {readiness.get('note', '')}")
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

    # Verify input is not mutated
    original = copy.deepcopy(snapshot)

    result = validate_issue(snapshot)

    # Assert read-only behavior
    if snapshot != original:
        fail("BUG: validate_issue mutated its input")

    _write_json(result)
    return EXIT_SUCCESS if result["valid"] else EXIT_ERROR


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

    # Verify input is not mutated
    original = copy.deepcopy(data)

    plan = build_change_plan(validation, evidence_raw, target, profile)

    if data != original:
        fail("BUG: build_change_plan mutated its input")

    _write_json(plan)
    return EXIT_SUCCESS


def cmd_check_enrichment(args: argparse.Namespace) -> int:
    """Run the check-enrichment subcommand."""
    data = _load_json(args.input)
    if not isinstance(data, dict):
        fail("input must be a JSON object")

    plan = data.get("plan")
    current = data.get("current_state")

    if not isinstance(plan, dict):
        fail("input.plan must be an object")
    if not isinstance(current, dict):
        fail("input.current_state must be an object")

    if args.readback:
        readback = _load_json(Path(args.readback))
        if not isinstance(readback, dict):
            fail("readback must be a JSON object")
        enrichment = check_enrichment(plan, current)
        receipt = verify_enrichment(enrichment, readback)
        _write_json({"enrichment": enrichment, "receipt": receipt})
    else:
        # Verify input is not mutated
        original = copy.deepcopy(data)
        result = check_enrichment(plan, current)
        if data != original:
            fail("BUG: check_enrichment mutated its input")
        _write_json(result)

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
    elif args.command == "build-plan":
        return cmd_build_plan(args)
    elif args.command == "check-enrichment":
        return cmd_check_enrichment(args)
    else:
        fail(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
