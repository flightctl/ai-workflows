#!/usr/bin/env bash
# Shared baseline validator for the rebase-stack workflow.
#
# Validates that a pre-rebase snapshot is structurally sound, matches the
# current repository identity, and covers the expected branch set. Used by
# push-guard.sh, stack-status.sh, and the /start, /validate, /push consumers.
#
# Usage:
#   validate-baseline.sh <baseline.json> [--remote <name>] [--context <ctx.json>]
#
# Without --context, performs schema-only validation (structure, types, SHA
# format). With --context, also checks repository identity (push URL, trunk,
# branch set) against the live Git state.
#
# Exit codes:
#   0  baseline is valid
#   1  baseline failed validation (details on stderr)
#   2  bad usage

set -uo pipefail

baseline=""
remote=""
ctx_file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --remote)   remote="${2:-}"; shift 2 ;;
    --context)  ctx_file="${2:-}"; shift 2 ;;
    -*)         echo "validate-baseline: unknown flag: $1" >&2; exit 2 ;;
    *)
      if [ -z "$baseline" ]; then
        baseline="$1"; shift
      else
        echo "validate-baseline: unexpected argument: $1" >&2; exit 2
      fi
      ;;
  esac
done

[ -n "$baseline" ] || { echo "validate-baseline: baseline path required" >&2; exit 2; }
[ -f "$baseline" ] || { echo "validate-baseline: file not found: ${baseline}" >&2; exit 1; }

# --- Schema validation -------------------------------------------------------

# Must be valid JSON
if ! jq -e '.' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: file is not valid JSON" >&2
  exit 1
fi

# Required top-level keys
for key in trunk baseRemote pushRemote pushUrl branches publishedTips; do
  if ! jq -e --arg k "$key" 'has($k)' "$baseline" >/dev/null 2>&1; then
    echo "validate-baseline: missing required key: $key" >&2
    exit 1
  fi
done

# Type checks
bl_trunk=$(jq -r '.trunk // empty' "$baseline")
bl_base_remote=$(jq -r '.baseRemote // empty' "$baseline")
bl_push_remote=$(jq -r '.pushRemote // empty' "$baseline")
bl_push_url=$(jq -r '.pushUrl // empty' "$baseline")

if [ -z "$bl_trunk" ]; then
  echo "validate-baseline: trunk is empty or null" >&2
  exit 1
fi
if [ -z "$bl_base_remote" ]; then
  echo "validate-baseline: baseRemote is empty or null" >&2
  exit 1
fi
if [ -z "$bl_push_remote" ]; then
  echo "validate-baseline: pushRemote is empty or null" >&2
  exit 1
fi

# publishedTips must be an object (not array, string, null, etc.)
pt_type=$(jq -r '.publishedTips | type' "$baseline" 2>/dev/null || echo "unknown")
if [ "$pt_type" != "object" ]; then
  echo "validate-baseline: publishedTips must be an object, got: $pt_type" >&2
  exit 1
fi

# publishedTips must not be empty
pt_count=$(jq '.publishedTips | length' "$baseline" 2>/dev/null || echo 0)
if [ "$pt_count" -eq 0 ]; then
  echo "validate-baseline: publishedTips is empty" >&2
  exit 1
fi

# Each value in publishedTips must be null (unpublished) or a 40-hex SHA
bad_values=$(jq -r '.publishedTips | to_entries[]
  | select(.value != null)
  | select((.value | type) != "string" or (.value | test("^[0-9a-f]{40}$") | not))
  | "\(.key): \(.value | tostring)"' "$baseline" 2>&1)
if [ -n "$bad_values" ]; then
  echo "validate-baseline: publishedTips contains malformed value(s):" >&2
  printf '  %s\n' "$bad_values" >&2
  exit 1
fi

# branches must be an array
br_type=$(jq -r '.branches | type' "$baseline" 2>/dev/null || echo "unknown")
if [ "$br_type" != "array" ]; then
  echo "validate-baseline: branches must be an array, got: $br_type" >&2
  exit 1
fi

# branches and publishedTips must cover the same set
br_names=$(jq -r '[.branches[].name] | sort | join(",")' "$baseline" 2>/dev/null || echo "")
pt_names=$(jq -r '.publishedTips | keys | sort | join(",")' "$baseline" 2>/dev/null || echo "")
if [ "$br_names" != "$pt_names" ]; then
  echo "validate-baseline: branches and publishedTips cover different sets" >&2
  echo "  branches:      $br_names" >&2
  echo "  publishedTips: $pt_names" >&2
  exit 1
fi

# --- Identity validation (requires --remote or --context) --------------------

if [ -n "$remote" ] && [ "$bl_push_remote" != "$remote" ]; then
  echo "validate-baseline: pushRemote '${bl_push_remote}' does not match --remote '${remote}'" >&2
  exit 1
fi

if [ -n "$ctx_file" ]; then
  [ -f "$ctx_file" ] || { echo "validate-baseline: context file not found: $ctx_file" >&2; exit 2; }

  # Check push URL matches current repository
  ctx_push_remote=$(jq -r '.pushRemote // empty' "$ctx_file")
  if [ -n "$ctx_push_remote" ]; then
    current_url=$(git remote get-url "$ctx_push_remote" 2>/dev/null || echo "")
    if [ -n "$bl_push_url" ] && [ -n "$current_url" ] && [ "$bl_push_url" != "$current_url" ]; then
      # Redact potential credentials from URLs in error messages
      safe_bl_url=$(printf '%s' "$bl_push_url" | sed 's|://[^@]*@|://***@|')
      safe_cur_url=$(printf '%s' "$current_url" | sed 's|://[^@]*@|://***@|')
      echo "validate-baseline: push URL mismatch (different repository?)" >&2
      echo "  baseline: $safe_bl_url" >&2
      echo "  current:  $safe_cur_url" >&2
      exit 1
    fi
  fi

  # Check trunk matches
  ctx_trunk=$(jq -r '.trunk // empty' "$ctx_file")
  if [ -n "$ctx_trunk" ] && [ "$bl_trunk" != "$ctx_trunk" ]; then
    echo "validate-baseline: trunk mismatch: baseline='${bl_trunk}' context='${ctx_trunk}'" >&2
    exit 1
  fi

  # Check push remote matches
  if [ -n "$ctx_push_remote" ] && [ "$bl_push_remote" != "$ctx_push_remote" ]; then
    echo "validate-baseline: pushRemote mismatch: baseline='${bl_push_remote}' context='${ctx_push_remote}'" >&2
    exit 1
  fi

  # Check branch set matches (order matters for stack)
  ctx_branches=$(jq -r '[.branches[].name] | join(",")' "$ctx_file" 2>/dev/null || echo "")
  bl_branches=$(jq -r '[.branches[].name] | join(",")' "$baseline" 2>/dev/null || echo "")
  if [ -n "$ctx_branches" ] && [ "$bl_branches" != "$ctx_branches" ]; then
    echo "validate-baseline: branch set mismatch" >&2
    echo "  baseline: $bl_branches" >&2
    echo "  context:  $ctx_branches" >&2
    exit 1
  fi
fi

exit 0
