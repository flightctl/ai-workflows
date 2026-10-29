#!/usr/bin/env bash
# Shared baseline validator for the rebase-stack workflow.
#
# Validates that a pre-rebase snapshot is structurally sound, matches the
# current repository identity, and covers the expected branch set.
#
# Usage:
#   validate-baseline.sh <baseline.json> --context <ctx.json> [--remote <name>]
#   validate-baseline.sh <baseline.json> --schema-only
#
# --context is REQUIRED by default. All production callers that authorize
# pushing must supply it. --schema-only is an explicit opt-in for callers
# that only need to check whether a file is a structurally valid baseline
# (e.g. snapshot overwrite protection). It must never authorize pushing.
#
# Exit codes:
#   0  baseline is valid
#   1  baseline failed validation (details on stderr)
#   2  bad usage

set -uo pipefail

baseline=""
remote=""
ctx_file=""
schema_only=false
while [ $# -gt 0 ]; do
  case "$1" in
    --remote)
      [ $# -ge 2 ] || { echo "validate-baseline: --remote requires a value" >&2; exit 2; }
      remote="$2"; shift 2 ;;
    --context)
      [ $# -ge 2 ] || { echo "validate-baseline: --context requires a value" >&2; exit 2; }
      ctx_file="$2"; shift 2 ;;
    --schema-only) schema_only=true; shift ;;
    -*)            echo "validate-baseline: unknown flag: $1" >&2; exit 2 ;;
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

# --context is required unless --schema-only is explicitly passed
if [ "$schema_only" != true ] && [ -z "$ctx_file" ]; then
  echo "validate-baseline: --context is required (use --schema-only for structure-only check)" >&2
  exit 2
fi

# === Baseline schema validation ==============================================

# Must be valid JSON object
if ! jq -e 'type == "object"' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: baseline is not a JSON object" >&2
  exit 1
fi

# Required top-level string fields — each must exist, be a string, and be non-empty
for key in trunk baseRemote pushRemote pushUrl gitCommonDir; do
  if ! jq -e --arg k "$key" '
    has($k) and (.[$k] | type == "string") and (.[$k] | length > 0)
  ' "$baseline" >/dev/null 2>&1; then
    echo "validate-baseline: baseline.$key must be a non-empty string" >&2
    exit 1
  fi
done

# publishedTips must be a non-empty object
if ! jq -e '.publishedTips | type == "object" and length > 0' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: publishedTips must be a non-empty object" >&2
  exit 1
fi

# Each publishedTips value must be null (unpublished) or a 40-hex SHA string
bad_values=$(jq -r '.publishedTips | to_entries[]
  | select(.value != null)
  | select((.value | type) != "string" or (.value | test("^[0-9a-f]{40}$") | not))
  | "\(.key): \(.value | tostring)"' "$baseline" 2>&1)
if [ -n "$bad_values" ]; then
  echo "validate-baseline: publishedTips contains malformed value(s):" >&2
  printf '  %s\n' "$bad_values" >&2
  exit 1
fi

# branches must be a non-empty array of objects with .name and .sha strings
if ! jq -e '
  .branches | type == "array" and length > 0
  and (all(type == "object" and (.name | type == "string") and (.name | length > 0)
       and has("sha") and (.sha | type == "string")))
' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: branches must be a non-empty array of {name,sha,...} objects" >&2
  exit 1
fi

# Branch names must be unique
if ! jq -e '[.branches[].name] | (unique | length) == length' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: branches array contains duplicates" >&2
  exit 1
fi

# branches[].name set must exactly match publishedTips keys
if ! jq -e '([.branches[].name] | sort) == (.publishedTips | keys | sort)' "$baseline" >/dev/null 2>&1; then
  echo "validate-baseline: branches and publishedTips cover different sets" >&2
  exit 1
fi

# === Context schema validation (when --context supplied) =====================

if [ -n "$ctx_file" ]; then
  [ -f "$ctx_file" ] || { echo "validate-baseline: context file not found: $ctx_file" >&2; exit 2; }

  # Context must be a JSON object with required non-empty string fields
  if ! jq -e '
    type == "object"
    and (.trunk | type == "string" and length > 0)
    and (.baseRemote | type == "string" and length > 0)
    and (.pushRemote | type == "string" and length > 0)
  ' "$ctx_file" >/dev/null 2>&1; then
    echo "validate-baseline: context must have non-empty string trunk, baseRemote, pushRemote" >&2
    exit 1
  fi

  # Context branches must be a non-empty array of objects with .name strings
  if ! jq -e '
    .branches | type == "array" and length > 0
    and (all(type == "object" and (.name | type == "string") and (.name | length > 0)))
  ' "$ctx_file" >/dev/null 2>&1; then
    echo "validate-baseline: context branches must be a non-empty array of {name,...} objects" >&2
    exit 1
  fi

  # Context branch names must be unique
  if ! jq -e '[.branches[].name] | (unique | length) == length' "$ctx_file" >/dev/null 2>&1; then
    echo "validate-baseline: context branches contain duplicates" >&2
    exit 1
  fi

  # --- Identity checks: none may be skipped ---

  bl_trunk=$(jq -r '.trunk' "$baseline")
  bl_base_remote=$(jq -r '.baseRemote' "$baseline")
  bl_push_remote=$(jq -r '.pushRemote' "$baseline")
  bl_push_url=$(jq -r '.pushUrl' "$baseline")
  bl_common_dir=$(jq -r '.gitCommonDir' "$baseline")
  ctx_trunk=$(jq -r '.trunk' "$ctx_file")
  ctx_base_remote=$(jq -r '.baseRemote' "$ctx_file")
  ctx_push_remote=$(jq -r '.pushRemote' "$ctx_file")

  # Trunk must match
  if [ "$bl_trunk" != "$ctx_trunk" ]; then
    echo "validate-baseline: trunk mismatch: baseline='${bl_trunk}' context='${ctx_trunk}'" >&2
    exit 1
  fi

  # baseRemote must match
  if [ "$bl_base_remote" != "$ctx_base_remote" ]; then
    echo "validate-baseline: baseRemote mismatch: baseline='${bl_base_remote}' context='${ctx_base_remote}'" >&2
    exit 1
  fi

  # pushRemote must match
  if [ "$bl_push_remote" != "$ctx_push_remote" ]; then
    echo "validate-baseline: pushRemote mismatch: baseline='${bl_push_remote}' context='${ctx_push_remote}'" >&2
    exit 1
  fi

  # --remote flag must match if supplied
  if [ -n "$remote" ] && [ "$bl_push_remote" != "$remote" ]; then
    echo "validate-baseline: pushRemote '${bl_push_remote}' does not match --remote '${remote}'" >&2
    exit 1
  fi

  # Ordered branch arrays must match exactly (commas are legal in branch names)
  if ! jq -e --slurpfile ctx "$ctx_file" '
    [.branches[].name] == [$ctx[0].branches[].name]
  ' "$baseline" >/dev/null 2>&1; then
    echo "validate-baseline: branch set/order mismatch" >&2
    echo "  baseline: $(jq -c '[.branches[].name]' "$baseline")" >&2
    echo "  context:  $(jq -c '[.branches[].name]' "$ctx_file")" >&2
    exit 1
  fi

  # Effective push URL must resolve to exactly one URL and match baseline
  push_url_count=$(git remote get-url --push --all "$ctx_push_remote" 2>/dev/null | wc -l)
  if [ "$push_url_count" -eq 0 ]; then
    echo "validate-baseline: could not resolve push URL for remote '${ctx_push_remote}'" >&2
    exit 1
  fi
  if [ "$push_url_count" -gt 1 ]; then
    echo "validate-baseline: remote '${ctx_push_remote}' has multiple push URLs; ambiguous" >&2
    exit 1
  fi
  current_url=$(git remote get-url --push "$ctx_push_remote")
  if [ "$bl_push_url" != "$current_url" ]; then
    safe_bl=$(printf '%s' "$bl_push_url" | sed 's|://[^@]*@|://***@|')
    safe_cur=$(printf '%s' "$current_url" | sed 's|://[^@]*@|://***@|')
    echo "validate-baseline: push URL mismatch (different repository?)" >&2
    echo "  baseline: $safe_bl" >&2
    echo "  current:  $safe_cur" >&2
    exit 1
  fi

  # Git common dir must resolve and match baseline
  current_common_dir=$(cd "$(git rev-parse --git-common-dir)" && pwd) \
    || { echo "validate-baseline: could not resolve git common dir" >&2; exit 1; }
  if [ "$bl_common_dir" != "$current_common_dir" ]; then
    echo "validate-baseline: git common dir mismatch (different checkout?)" >&2
    echo "  baseline: $bl_common_dir" >&2
    echo "  current:  $current_common_dir" >&2
    exit 1
  fi
fi

exit 0
