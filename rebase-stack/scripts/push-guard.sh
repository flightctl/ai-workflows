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
#   push-guard.sh --baseline <file> --remote <remote> --context <ctx.json>
#
# Exit codes: passes through gh stack push's exit code.
#   2  bad usage, baseline missing/invalid, or hook setup failed

set -uo pipefail

baseline=""
remote=""
ctx_file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --baseline)
      [ $# -ge 2 ] || { echo "push-guard: --baseline requires a value" >&2; exit 2; }
      baseline="$2"; shift 2 ;;
    --remote)
      [ $# -ge 2 ] || { echo "push-guard: --remote requires a value" >&2; exit 2; }
      remote="$2"; shift 2 ;;
    --context)
      [ $# -ge 2 ] || { echo "push-guard: --context requires a value" >&2; exit 2; }
      ctx_file="$2"; shift 2 ;;
    *) echo "push-guard: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$baseline" ] || { echo "push-guard: --baseline is required" >&2; exit 2; }
[ -n "$remote" ]   || { echo "push-guard: --remote is required" >&2; exit 2; }
[ -n "$ctx_file" ] || { echo "push-guard: --context is required" >&2; exit 2; }
[ -f "$baseline" ] || { echo "push-guard: baseline file not found: ${baseline}" >&2; exit 2; }
[ -f "$ctx_file" ] || { echo "push-guard: context file not found: ${ctx_file}" >&2; exit 2; }

# --- Validate baseline schema and identity --------------------------------
scripts_dir="$(cd "$(dirname "$0")" && pwd)"
if ! bash "$scripts_dir/validate-baseline.sh" "$baseline" --remote "$remote" --context "$ctx_file"; then
  echo "push-guard: baseline validation failed" >&2
  exit 2
fi

# Absolute path for baseline (hook may run in a different cwd)
baseline=$(cd "$(dirname "$baseline")" && printf '%s/%s' "$(pwd)" "$(basename "$baseline")")

# --- Resolve the ORIGINAL hooks directory ---------------------------------
# For linked worktrees, hooks live in the common dir (the main .git directory),
# not in the per-worktree .git/worktrees/<name>/ directory. git-common-dir
# gives the right location in all cases (root worktree and linked worktrees).
# Canonicalize to absolute path: git-common-dir may return a relative path
# when invoked from a subdirectory.
original_hooks_dir=""
if chp=$(git config core.hooksPath 2>/dev/null) && [ -n "$chp" ]; then
  case "$chp" in
    /*) original_hooks_dir="$chp" ;;
    *)  original_hooks_dir="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/$chp" ;;
  esac
else
  original_hooks_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd)/hooks"
fi

# Invoke original hook at its ORIGINAL path to preserve $0/symlink behavior.
# Do NOT use readlink -f: it resolves symlinks and changes the invocation path,
# which breaks hooks that use $0 or dirname to locate sibling scripts.
original_pre_push=""
if [ -x "$original_hooks_dir/pre-push" ]; then
  original_pre_push="$original_hooks_dir/pre-push"
fi

# --- Create per-invocation temporary hooks directory ----------------------
guard_dir=$(mktemp -d "${TMPDIR:-/tmp}/rebase-stack-guard.XXXXXX") \
  || { echo "push-guard: could not create temporary directory" >&2; exit 2; }

cleanup() {
  rm -rf "$guard_dir"
}
# On signals, clean up AND exit with the signal's conventional code.
# Without the explicit exit, bash continues after the trap handler.
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap 'cleanup; exit 129' HUP

# --- Chain other applicable hooks from the original hooks directory --------
# core.hooksPath overrides the ENTIRE hooks directory, not just one hook.
# To avoid silently bypassing other hooks (e.g. reference-transaction), create
# thin wrappers for all executable hooks EXCEPT pre-push (which we replace).
# printf %q safely quotes the hook path so shell metacharacters in paths
# (quotes, dollars, backticks) cannot become executable code.
if [ -d "$original_hooks_dir" ]; then
  for hook_file in "$original_hooks_dir"/*; do
    [ -x "$hook_file" ] || continue
    hook_name=$(basename "$hook_file")
    [ "$hook_name" != "pre-push" ] || continue
    if ! printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$hook_file" \
         > "$guard_dir/$hook_name"; then
      echo "push-guard: could not write hook wrapper: $hook_name" >&2
      exit 2
    fi
    if ! chmod +x "$guard_dir/$hook_name"; then
      echo "push-guard: could not chmod hook wrapper: $hook_name" >&2
      exit 2
    fi
  done
fi

# --- Write the ephemeral pre-push hook ------------------------------------
# The inner hook must also validate the baseline fully (not just publishedTips
# type check) because the baseline file could be modified between the outer
# check and the actual push. Use the same shared validator via env var path.
if ! cat > "$guard_dir/pre-push" << 'HOOKEOF'
#!/usr/bin/env bash
# Ephemeral pre-push hook — validates advertised remote OIDs against baseline.
# Chains to the original pre-push hook with byte-identical stdin and argv.
set -uo pipefail

ZERO="0000000000000000000000000000000000000000"
baseline_file="${REBASE_STACK_BASELINE_FILE:-}"
original_hook="${REBASE_STACK_ORIGINAL_HOOK:-}"
validator="${REBASE_STACK_VALIDATOR:-}"
context_file="${REBASE_STACK_CONTEXT_FILE:-}"

# Preserve stdin byte-for-byte in a temp file so both the original hook and
# our check see the exact same bytes, including any trailing newline.
stdin_file=$(mktemp "${TMPDIR:-/tmp}/rebase-stack-stdin.XXXXXX")
if [ $? -ne 0 ]; then
  echo "rebase-stack pre-push: cannot create stdin temp file" >&2
  exit 1
fi
stdin_cleanup() { rm -f "$stdin_file"; }
trap 'stdin_cleanup; exit 130' INT
trap 'stdin_cleanup; exit 143' TERM
trap stdin_cleanup EXIT
if ! cat > "$stdin_file"; then
  echo "rebase-stack pre-push: cannot capture stdin" >&2
  exit 1
fi

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

# Full validation using the shared validator with context — no fallback.
# Both must be readable; the validator is invoked via bash (no +x needed).
if [ -z "$validator" ] || [ ! -r "$validator" ]; then
  echo "rebase-stack pre-push: validator missing or unreadable; refusing push" >&2
  exit 1
fi
if [ -z "$context_file" ] || [ ! -f "$context_file" ]; then
  echo "rebase-stack pre-push: context file missing; refusing push" >&2
  exit 1
fi
if ! bash "$validator" "$baseline_file" --context "$context_file" --remote "$1" >/dev/null 2>&1; then
  echo "rebase-stack pre-push: baseline failed validation at push time; refusing" >&2
  exit 1
fi

# Guard ALL refs being pushed. A branch in publishedTips is checked against
# its saved OID; a branch NOT in publishedTips is unknown to the active stack
# and is rejected outright — fail closed, never skip. The snapshot records
# every intended branch (published OID or null for unpublished), so absence
# from publishedTips means the branch was not part of the validated stack.
failed=0

# Compare the actual push destination URL ($2, from Git's wire protocol)
# against the baseline's saved pushUrl. This closes the window where the
# push URL config could change between the outer/inner validator checks
# (which read from config) and the actual push destination.
actual_push_url="${2:-}"
saved_push_url=$(jq -r '.pushUrl // empty' "$baseline_file")
if [ -n "$actual_push_url" ] && [ -n "$saved_push_url" ] \
   && [ "$actual_push_url" != "$saved_push_url" ]; then
  printf 'rebase-stack pre-push: actual push destination does not match baseline for remote %s; refusing\n' \
    "${1:-unknown}" >&2
  failed=1
fi
while IFS=' ' read -r _local_ref _local_sha remote_ref remote_sha; do
  [ -n "$remote_ref" ] || continue
  branch="${remote_ref#refs/heads/}"
  [ "$branch" != "$remote_ref" ] || continue

  has_key=$(jq -r --arg b "$branch" '.publishedTips | has($b)' "$baseline_file")
  if [ "$has_key" != "true" ]; then
    printf 'rebase-stack pre-push: %s is not in the validated stack baseline; refusing\n' \
      "$branch" >&2
    failed=1
    continue
  fi

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
then
  echo "push-guard: could not write ephemeral pre-push hook" >&2
  exit 2
fi
chmod +x "$guard_dir/pre-push" \
  || { echo "push-guard: could not chmod ephemeral pre-push hook" >&2; exit 2; }

# --- Export state for the hook --------------------------------------------
export REBASE_STACK_BASELINE_FILE="$baseline"
export REBASE_STACK_ORIGINAL_HOOK="$original_pre_push"
export REBASE_STACK_VALIDATOR="$scripts_dir/validate-baseline.sh"
REBASE_STACK_CONTEXT_FILE=$(cd "$(dirname "$ctx_file")" && printf '%s/%s' "$(pwd)" "$(basename "$ctx_file")")
export REBASE_STACK_CONTEXT_FILE

# --- Inject the temporary hooks directory via GIT_CONFIG_* ----------------
existing_count="${GIT_CONFIG_COUNT:-0}"
new_index="$existing_count"
export GIT_CONFIG_COUNT=$((existing_count + 1))
export "GIT_CONFIG_KEY_${new_index}=core.hooksPath"
export "GIT_CONFIG_VALUE_${new_index}=${guard_dir}"

# --- Verify effective hooksPath actually points to the guard dir ----------
# GIT_CONFIG_PARAMETERS takes precedence over GIT_CONFIG_COUNT for the same
# key. If a parent process already set core.hooksPath via PARAMETERS, our
# COUNT-based override is silently ignored and the guard hook never runs.
# Fail closed rather than delegating unguarded.
effective_hooks=$(git config core.hooksPath 2>/dev/null || echo "")
if [ "$effective_hooks" != "$guard_dir" ]; then
  echo "push-guard: effective core.hooksPath is '${effective_hooks}', not the guard dir" >&2
  echo "  A parent process may have set core.hooksPath via GIT_CONFIG_PARAMETERS." >&2
  echo "  The guard hook would be bypassed. Refusing to push." >&2
  exit 2
fi

# --- Delegate to gh stack push --------------------------------------------
gh stack push --remote "$remote"
