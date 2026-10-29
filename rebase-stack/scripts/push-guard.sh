#!/usr/bin/env bash
# Ephemeral pre-push baseline guard for the rebase-stack workflow.
#
# Creates a per-invocation temporary hooks directory containing a pre-push
# hook that validates Git's advertised remote OIDs against the saved
# pre-rebase baseline. The temporary directory is injected via GIT_CONFIG_*
# environment variables (core.hooksPath override), so the original hooks
# directory, its files, symlinks, and any concurrent push-guard invocations
# are never touched. The override reaches the child git invoked by gh-stack
# because Go's exec.Cmd inherits the parent environment.
#
# The hook chains to the original pre-push hook (resolved at its original
# path, never copied) with byte-identical stdin replay and unchanged argv.
# If the original hook rejects, the push is aborted before the baseline
# check runs. After the baseline check passes, Git's --force-with-lease
# covers the remaining window between advertisement and data transfer.
#
# Usage:
#   push-guard.sh --baseline <file> --remote <remote>
#
# Exit codes: passes through gh stack push's exit code.
#   2  bad usage, baseline missing/invalid, or hook setup failed

set -uo pipefail

baseline=""
remote=""
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline) baseline="${2:-}"; shift 2 ;;
    --remote)   remote="${2:-}"; shift 2 ;;
    *) echo "push-guard: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$baseline" ] || { echo "push-guard: --baseline is required" >&2; exit 2; }
[ -n "$remote" ]   || { echo "push-guard: --remote is required" >&2; exit 2; }
[ -f "$baseline" ] || { echo "push-guard: baseline file not found: ${baseline}" >&2; exit 2; }

# --- Validate baseline schema and identity --------------------------------
if ! jq -e 'if .publishedTips | type == "object" then true else false end' \
     "$baseline" >/dev/null 2>&1; then
  echo "push-guard: baseline publishedTips is missing or not an object" >&2
  exit 2
fi
bad_shas=$(jq -r '.publishedTips | to_entries[]
  | select(.value != null)
  | select(.value | test("^[0-9a-f]{40}$") | not)
  | "\(.key): \(.value)"' "$baseline" 2>/dev/null)
if [ -n "$bad_shas" ]; then
  echo "push-guard: baseline contains malformed SHA(s):" >&2
  printf '  %s\n' "$bad_shas" >&2
  exit 2
fi
bl_trunk=$(jq -r '.trunk // empty' "$baseline")
bl_push_remote=$(jq -r '.pushRemote // empty' "$baseline")
if [ -z "$bl_trunk" ] || [ -z "$bl_push_remote" ]; then
  echo "push-guard: baseline missing trunk or pushRemote identity" >&2
  exit 2
fi
if [ "$bl_push_remote" != "$remote" ]; then
  echo "push-guard: baseline pushRemote '${bl_push_remote}' does not match --remote '${remote}'" >&2
  exit 2
fi

# Absolute path for baseline (hook may run in a different cwd)
baseline=$(cd "$(dirname "$baseline")" && printf '%s/%s' "$(pwd)" "$(basename "$baseline")")

# --- Resolve the ORIGINAL hooks directory ---------------------------------
original_hooks_dir=""
if chp=$(git config core.hooksPath 2>/dev/null) && [ -n "$chp" ]; then
  case "$chp" in
    /*) original_hooks_dir="$chp" ;;
    *)  original_hooks_dir="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/$chp" ;;
  esac
else
  original_hooks_dir="$(git rev-parse --absolute-git-dir)/hooks"
fi

original_pre_push=""
if [ -x "$original_hooks_dir/pre-push" ]; then
  original_pre_push=$(readlink -f "$original_hooks_dir/pre-push" 2>/dev/null \
    || printf '%s/pre-push' "$original_hooks_dir")
fi

# --- Create per-invocation temporary hooks directory ----------------------
guard_dir=$(mktemp -d "${TMPDIR:-/tmp}/rebase-stack-guard.XXXXXX") \
  || { echo "push-guard: could not create temporary directory" >&2; exit 2; }

cleanup() { rm -rf "$guard_dir"; }
trap cleanup EXIT

# --- Write the ephemeral pre-push hook ------------------------------------
cat > "$guard_dir/pre-push" << 'HOOKEOF'
#!/usr/bin/env bash
# Ephemeral pre-push hook — validates advertised remote OIDs against baseline.
# Chains to the original pre-push hook with byte-identical stdin and argv.
set -uo pipefail

ZERO="0000000000000000000000000000000000000000"
baseline_file="${REBASE_STACK_BASELINE_FILE:-}"
original_hook="${REBASE_STACK_ORIGINAL_HOOK:-}"

# Preserve stdin byte-for-byte in a temp file so both the original hook and
# our check see the exact same bytes, including any trailing newline.
stdin_file=$(mktemp "${TMPDIR:-/tmp}/rebase-stack-stdin.XXXXXX") \
  || { echo "rebase-stack pre-push: cannot create stdin temp file" >&2; exit 1; }
stdin_cleanup() { rm -f "$stdin_file"; }
trap stdin_cleanup EXIT
cat > "$stdin_file"

# ------ Chain: run original hook with unchanged args and exact stdin ------
if [ -n "$original_hook" ] && [ -x "$original_hook" ]; then
  "$original_hook" "$@" < "$stdin_file"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    exit "$rc"
  fi
fi

# ------ Baseline guard ---------------------------------------------------
if [ -z "$baseline_file" ] || [ ! -f "$baseline_file" ]; then
  echo "rebase-stack pre-push: baseline file missing; refusing push" >&2
  exit 1
fi
if ! jq -e 'if .publishedTips | type == "object" then true else false end' \
     "$baseline_file" >/dev/null 2>&1; then
  echo "rebase-stack pre-push: baseline invalid; refusing push" >&2
  exit 1
fi

# Guard only refs whose branch name appears in publishedTips (known branches).
# An unknown branch (not in publishedTips at all) is not guarded — it may be
# a new branch created after the snapshot and is outside the baseline's scope.
failed=0
while IFS=' ' read -r _local_ref _local_sha remote_ref remote_sha; do
  [ -n "$remote_ref" ] || continue
  branch="${remote_ref#refs/heads/}"
  [ "$branch" != "$remote_ref" ] || continue

  has_key=$(jq -r --arg b "$branch" '.publishedTips | has($b)' "$baseline_file")
  [ "$has_key" = "true" ] || continue

  saved_tip=$(jq -r --arg b "$branch" '.publishedTips[$b] // "null"' "$baseline_file")

  if [ "$saved_tip" = "null" ]; then
    if [ "$remote_sha" != "$ZERO" ]; then
      printf 'rebase-stack pre-push: %s was unpublished but remote advertises %s; refusing\n' \
        "$branch" "${remote_sha:0:12}" >&2
      failed=1
    fi
  else
    if [ "$remote_sha" = "$ZERO" ]; then
      printf 'rebase-stack pre-push: %s was at baseline %s but deleted from remote; refusing\n' \
        "$branch" "${saved_tip:0:12}" >&2
      failed=1
    elif [ "$remote_sha" != "$saved_tip" ]; then
      printf 'rebase-stack pre-push: %s remote changed: baseline=%s advertised=%s; refusing\n' \
        "$branch" "${saved_tip:0:12}" "${remote_sha:0:12}" >&2
      failed=1
    fi
  fi
done < "$stdin_file"

exit "$failed"
HOOKEOF
chmod +x "$guard_dir/pre-push"

# --- Export state for the hook --------------------------------------------
export REBASE_STACK_BASELINE_FILE="$baseline"
export REBASE_STACK_ORIGINAL_HOOK="$original_pre_push"

# --- Inject the temporary hooks directory via GIT_CONFIG_* ----------------
existing_count="${GIT_CONFIG_COUNT:-0}"
new_index="$existing_count"
export GIT_CONFIG_COUNT=$((existing_count + 1))
export "GIT_CONFIG_KEY_${new_index}=core.hooksPath"
export "GIT_CONFIG_VALUE_${new_index}=${guard_dir}"

# --- Delegate to gh stack push --------------------------------------------
gh stack push --remote "$remote"
