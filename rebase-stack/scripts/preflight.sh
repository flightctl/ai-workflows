#!/usr/bin/env bash
# Hard gate for the rebase-stack workflow.
#
# Verifies the required tooling, proves the caller is really inside a
# gh-stack-tracked stack, and resolves which remotes to use. Emits a single
# JSON context object on stdout; all diagnostics go to stderr.
#
# Any non-zero exit means the workflow MUST stop. There is no fallback path:
# nothing here installs tooling, initializes a stack, or guesses a remote.
#
# Usage:
#   preflight.sh [--allow-rebase-in-progress]
#
# Exit codes:
#   0   all gates passed; JSON context on stdout
#   2   not in a gh-stack stack (refuse — this is not a stack rebase)
#   3   a rebase is already in progress (and --allow-rebase-in-progress unset)
#   4   GitHub API failure or gh not authenticated
#   6   branch belongs to multiple stacks; disambiguation required
#   7   dirty working tree
#   8   required tooling missing
#   9   remote could not be resolved unambiguously
#   1   anything else

set -uo pipefail

allow_rebase=0
case "${1:-}" in
  --allow-rebase-in-progress) allow_rebase=1 ;;
  "") ;;
  *) printf 'preflight: unknown argument: %s\n' "$1" >&2; exit 1 ;;
esac

die() {
  printf '\nrebase-stack preflight FAILED\n  %s\n' "$1" >&2
  exit "${2:-1}"
}

# --------------------------------------------------------------------------
# Gate 1 — required tooling. Hard requirements, never auto-installed.
# --------------------------------------------------------------------------
command -v git >/dev/null 2>&1 || die "git is not installed." 8
command -v jq  >/dev/null 2>&1 || die "jq is not installed. Install jq, then retry." 8
command -v gh  >/dev/null 2>&1 || die "GitHub CLI (gh) is not installed. See https://cli.github.com/" 8

# The exit code cannot be used here. When the extension is NOT installed, gh
# recognizes 'stack' as a known official extension and prints an advisory for
# every invocation — `gh stack --help`, `--version`, even `view --json` — and
# exits 0. Detection has to read the output. Verified against gh 2.92.0.
stack_version=$(gh stack --version 2>&1)
case "$stack_version" in
  *"gh extension install"*|*"available as an official extension"*)
    die "'gh stack' is not installed.
  gh recognizes the name and exits 0 with an advisory, which is why this is
  checked by output rather than exit code. This workflow is built on gh-stack
  and has no fallback path. Install it and retry:
      gh extension install github/gh-stack" 8 ;;
esac
printf '%s' "$stack_version" | grep -qE '[0-9]+\.[0-9]+' || die \
  "Could not confirm 'gh stack' is installed. 'gh stack --version' printed:
      ${stack_version}
  Expected a version string. Install or repair the extension and retry:
      gh extension install github/gh-stack" 8

# --------------------------------------------------------------------------
# Gate 2 — repository context.
# --------------------------------------------------------------------------
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "Not inside a git repository." 1

git_dir=$(git rev-parse --git-dir)
rebase_in_progress=false
if [ -d "$git_dir/rebase-merge" ] || [ -d "$git_dir/rebase-apply" ]; then
  rebase_in_progress=true
fi

if [ "$rebase_in_progress" = true ] && [ "$allow_rebase" -eq 0 ]; then
  die "A rebase is already in progress.
  Resolve the conflict and run /continue, or abandon it with:
      gh stack rebase --abort" 3
fi

if [ "$rebase_in_progress" = false ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  die "The working tree has uncommitted tracked changes.
  Commit or stash them before rebasing:
      git stash push -m 'pre rebase-stack'" 7
fi

# --------------------------------------------------------------------------
# Gate 3 — ACTIVATION GATE. Refuse unless this is a real tracked stack.
# --------------------------------------------------------------------------
# Keep stderr: for an unhandled exit code the message below is all the user
# gets, and "exited 5" without gh's own reason leaves them nothing to act on.
stack_err=$(mktemp "${TMPDIR:-/tmp}/rebase-stack-preflight.XXXXXX") \
  || die "Could not create a temporary file for gh diagnostics." 1
stack_json=$(gh stack view --json 2>"$stack_err")
rc=$?
stack_diag=$(head -5 "$stack_err" | sed '2,$s/^/      /')
rm -f "$stack_err"
case "$rc" in
  0) ;;
  2) die "The current branch is not part of a gh-stack stack.
  This workflow only rebases tracked stacks. It will not initialize one for you
  and it is not a replacement for rebasing a single branch. For a single branch:
      git fetch <remote> && git rebase <remote>/<base>
  To adopt an existing chain of branches as a stack first:
      gh stack init --base <base> <bottom-branch> ... <top-branch>" 2 ;;
  6) die "This branch belongs to more than one stack.
  Check out a branch unique to the stack you want to rebase:
      gh stack checkout <branch>" 6 ;;
  4) die "GitHub API failure. Check authentication and retry:
      gh auth status" 4 ;;
  *) die "'gh stack view --json' exited $rc. Stopping; the stack state is unknown.
  gh reported:
      ${stack_diag:-(no output on stderr)}" "$rc" ;;
esac

if ! jq -e . >/dev/null 2>&1 <<<"$stack_json"; then
  # Exit 0 with non-JSON output is the signature of the missing-extension
  # advisory. Gate 1 should have caught it; say so plainly rather than
  # reporting a parse error.
  die "'gh stack view --json' exited 0 but did not produce JSON:
      $(printf '%s' "$stack_json" | head -1)
  This is what gh prints when the gh-stack extension is not installed:
      gh extension install github/gh-stack" 8
fi

trunk=$(jq -r '.trunk // empty' <<<"$stack_json")
current=$(jq -r '.currentBranch // empty' <<<"$stack_json")
[ -n "$trunk" ] || die "'gh stack view --json' returned no trunk. Stopping." 1

unmerged_count=$(jq '[.branches[]? | select(.isMerged != true)] | length' <<<"$stack_json")
case "$unmerged_count" in
  ''|*[!0-9]*) die "Could not count unmerged branches in the stack. Stopping." 1 ;;
esac
if [ "$unmerged_count" -eq 0 ]; then
  die "Every branch in this stack is already merged. There is nothing to rebase.
  Remove the local stack with 'gh stack unstack --local' when you are done with it." 2
fi
if [ "$unmerged_count" -lt 2 ]; then
  die "This stack has only one unmerged branch, so there is nothing stacked to
  rebase. Rebase it directly instead:
      git fetch <remote> && git rebase <remote>/${trunk}" 2
fi

# --------------------------------------------------------------------------
# Gate 4 — remote resolution. Never assume 'origin'.
# --------------------------------------------------------------------------
remotes=$(git remote)
remote_count=$(printf '%s\n' "$remotes" | grep -c . || true)
[ "$remote_count" -gt 0 ] || die "No git remotes are configured." 9

pick_preferred() {
  # Deterministic tiebreak when several remotes carry the same ref.
  local candidates="$1" preferred
  for preferred in upstream origin; do
    if printf '%s\n' "$candidates" | grep -qx "$preferred"; then
      printf '%s' "$preferred"
      return 0
    fi
  done
  return 1
}

# base remote — where the trunk the stack targets actually lives.
base_remote=""
base_remote_source=""

if upstream_ref=$(git rev-parse --abbrev-ref --symbolic-full-name "${trunk}@{upstream}" 2>/dev/null) \
   && [ -n "$upstream_ref" ]; then
  base_remote="${upstream_ref%%/*}"
  base_remote_source="upstream tracking ref of ${trunk}"
fi

if [ -z "$base_remote" ]; then
  if cfg=$(git config --get "branch.${trunk}.remote" 2>/dev/null) && [ -n "$cfg" ]; then
    base_remote="$cfg"
    base_remote_source="branch.${trunk}.remote"
  fi
fi

if [ -z "$base_remote" ]; then
  carriers=$(git for-each-ref --format='%(refname:strip=2)' "refs/remotes/*/${trunk}" \
             | sed "s|/${trunk}\$||" | sort -u)
  carrier_count=$(printf '%s\n' "$carriers" | grep -c . || true)
  if [ "$carrier_count" -eq 1 ]; then
    base_remote="$carriers"
    base_remote_source="only remote carrying ${trunk}"
  elif [ "$carrier_count" -gt 1 ]; then
    if base_remote=$(pick_preferred "$carriers"); then
      base_remote_source="preferred among remotes carrying ${trunk}"
    fi
  fi
fi

if [ -z "$base_remote" ] && [ "$remote_count" -eq 1 ]; then
  base_remote="$remotes"
  base_remote_source="only configured remote"
fi

[ -n "$base_remote" ] || die "Cannot determine which remote hosts the base branch '${trunk}'.
  Candidates: $(printf '%s' "$remotes" | tr '\n' ' ')
  Set the tracking ref explicitly, then retry:
      git branch --set-upstream-to=<remote>/${trunk} ${trunk}" 9

# push remote — where this stack's branches are published. In a fork workflow
# this is NOT the same remote as the base branch.
push_remote=""
push_remote_source=""

if cfg=$(git config --get remote.pushDefault 2>/dev/null) && [ -n "$cfg" ] \
   && git remote get-url "$cfg" >/dev/null 2>&1; then
  push_remote="$cfg"
  push_remote_source="remote.pushDefault"
fi

if [ -z "$push_remote" ] && [ -n "$current" ]; then
  if pref=$(git rev-parse --abbrev-ref --symbolic-full-name "${current}@{push}" 2>/dev/null) \
     && [ -n "$pref" ]; then
    push_remote="${pref%%/*}"
    push_remote_source="push ref of ${current}"
  fi
fi

if [ -z "$push_remote" ] && [ "$remote_count" -eq 1 ]; then
  push_remote="$remotes"
  push_remote_source="only configured remote"
fi

if [ -z "$push_remote" ]; then
  die "Cannot determine which remote this stack is published to.
  It is NOT safe to default to the base remote '${base_remote}': in a fork
  workflow that would force-push your branches over the upstream. Set it
  explicitly, then retry:
      git config remote.pushDefault <remote>
  Configured remotes: $(printf '%s' "$remotes" | tr '\n' ' ')" 9
fi

for r in "$base_remote" "$push_remote"; do
  if ! git remote get-url "$r" >/dev/null 2>&1; then
    die "Resolved remote '$r' is not a configured remote.
  It came from: $([ "$r" = "$base_remote" ] && printf '%s' "$base_remote_source" \
                   || printf '%s' "$push_remote_source")
  Configured remotes: $(printf '%s' "$remotes" | tr '\n' ' ')" 9
  fi
done

if [ "$remote_count" -gt 1 ] && [ -z "$(git config --get remote.pushDefault)" ]; then
  printf 'preflight: WARNING: %s remotes configured and remote.pushDefault is unset.\n' \
    "$remote_count" >&2
  printf "preflight: every gh stack call below passes --remote explicitly.\n" >&2
fi

# --------------------------------------------------------------------------
# Repository topology (fork awareness). Non-fatal: push reporting only.
# --------------------------------------------------------------------------
push_url=$(git remote get-url "$push_remote" 2>/dev/null || true)
repo_json='{}'
if [ -n "$push_url" ]; then
  repo_json=$(gh repo view "$push_url" --json isFork,nameWithOwner,owner,parent 2>/dev/null || echo '{}')
fi

# --------------------------------------------------------------------------
# Emit context.
# --------------------------------------------------------------------------
jq -n \
  --argjson stack "$stack_json" \
  --argjson repo "$repo_json" \
  --arg baseRemote "$base_remote" \
  --arg baseRemoteSource "$base_remote_source" \
  --arg pushRemote "$push_remote" \
  --arg pushRemoteSource "$push_remote_source" \
  --argjson rebaseInProgress "$rebase_in_progress" \
  '{
     trunk:             $stack.trunk,
     currentBranch:     $stack.currentBranch,
     baseRemote:        $baseRemote,
     baseRemoteSource:  $baseRemoteSource,
     pushRemote:        $pushRemote,
     pushRemoteSource:  $pushRemoteSource,
     rebaseInProgress:  $rebaseInProgress,
     isFork:            ($repo.isFork // null),
     repo:              ($repo.nameWithOwner // null),
     forkOwner:         ($repo.owner.login // null),
     parentRepo:        ($repo.parent.nameWithOwner // null),
     branches:          [$stack.branches[] | select(.isMerged != true)
                          | {name, needsRebase, pr: (.pr.number // null), prState: (.pr.state // null)}],
     mergedBranches:    [$stack.branches[] | select(.isMerged == true) | .name]
   }
   | .bottomBranch       = (.branches[0].name // null)
   | .validationBranch   = (.branches[0].name // null)
   | .needsRebaseCount   = ([.branches[] | select(.needsRebase == true)] | length)'
