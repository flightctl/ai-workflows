#!/usr/bin/env bash
# Deterministic publish operations for ai-workflows.
#
# Provides reusable subcommands for the publish/PR/MR phase of multiple
# workflows (bugfix, implement, e2e, prd, design, docs-writer). Each
# subcommand handles one discrete, deterministic operation — the calling
# skill file retains ownership of AI-dependent work (PR body generation,
# cross-cutting review, user confirmation prompts).
#
# Subcommands:
#   preflight       Pre-flight checks (auth, branch, uncommitted changes)
#   push            Push a branch to a remote
#   check-existing  Check whether a PR/MR already exists for a branch
#   create-pr       Create a GitHub pull request via gh CLI
#   create-mr       Create a GitLab merge request via glab CLI
#   save-metadata   Write publish-metadata.json
#
# Usage:
#   publish.sh preflight [--platform github|gitlab]
#   publish.sh push --remote <name> --branch <branch>
#   publish.sh check-existing --repo <owner/repo> --head <branch> [--platform github|gitlab]
#   publish.sh create-pr --repo <owner/repo> --base <branch> --head <ref> \
#              --title <title> [--body-file <path>] [--body <text>] [--draft] [--labels <csv>]
#   publish.sh create-mr --project <path> --source <branch> --target <branch> \
#              --title <title> [--description <text>] [--draft]
#   publish.sh save-metadata --file <path> [key=value ...]
#
# Exit codes:
#   0 — success (preflight reports issues via structured output, not exit codes)
#   1 — missing argument or configuration error
#   3 — push failed
#   4 — PR/MR creation failed
#   5 — existing PR/MR found (check-existing only; prints details on stdout)

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Print an error message to stderr and exit with the given code.
fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit "${2:-1}"
}

# Print an informational message to stderr.
info() {
  printf 'INFO: %s\n' "$1" >&2
}

# Print usage information extracted from the script header and exit.
usage() {
  sed -n '/^# Usage:/,/^# Exit codes:/{ /^# Exit codes:/d; s/^# \?//; p }' "$0" >&2
  exit 1
}

# Fail with a descriptive message if a required argument is empty.
require_arg() {
  if [[ -z "${2:-}" ]]; then
    fail "Missing required argument: $1" 1
  fi
}

# Validate that a CLI flag has an accompanying value argument.
flag_value() {
  # Prevents cryptic "unbound variable" errors under set -u when a flag
  # is passed without its value (e.g., --platform with no argument).
  # Usage (inside a while/case loop): flag_value "--flag-name" "$#"
  if [[ $2 -lt 2 ]]; then
    fail "$1 requires a value" 1
  fi
}

# Escape a string for safe embedding as a JSON string value.
# Handles backslash, double-quote, newline, tab, carriage return, and
# other control characters (0x00-0x1F, 0x7F) using \uXXXX notation.
# Does not add surrounding quotes — the caller wraps the result.
json_escape() {
  local s="$1"
  local out=""
  local i char code
  for (( i = 0; i < ${#s}; i++ )); do
    char="${s:i:1}"
    case "$char" in
      \\)      out+="\\\\" ;;
      '"')     out+="\\\"" ;;
      $'\n')   out+="\\n" ;;
      $'\t')   out+="\\t" ;;
      $'\r')   out+="\\r" ;;
      $'\b')   out+="\\b" ;;
      $'\x0c') out+="\\f" ;;
      *)
        # Detect remaining control characters (0x00-0x1F, 0x7F)
        printf -v code '%d' "'${char}"
        if (( code >= 0 && code < 32 )) || (( code == 127 )); then
          printf -v char '\\u%04x' "$code"
          out+="${char}"
        else
          out+="${char}"
        fi
        ;;
    esac
  done
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# Subcommand: preflight
# ---------------------------------------------------------------------------
# Run pre-flight checks: auth, branch, and working-tree cleanliness.
# Prints a structured key=value status block on stdout for the calling
# skill to parse.
#
# Flags:
#   --platform github|gitlab   Which CLI to check (default: github)

cmd_preflight() {
  local platform="github"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --platform) flag_value "$1" "$#"; platform="$2"; shift 2 ;;
      *) fail "preflight: unknown flag: $1" 1 ;;
    esac
  done

  local auth_ok="false"
  local auth_user=""
  local branch=""
  local has_uncommitted="false"
  local has_staged="false"
  local has_untracked="false"

  # -- Auth check --
  case "$platform" in
    github)
      if gh auth status >/dev/null 2>&1; then
        auth_ok="true"
        auth_user=$(gh api user --jq .login 2>/dev/null || true)
        if [[ -z "$auth_user" ]]; then
          # GitHub App / bot — try installation endpoint
          auth_user=$(gh api /installation/repositories \
            --jq '.repositories[0].owner.login' 2>/dev/null || true)
        fi
      fi
      ;;
    gitlab)
      if glab auth status >/dev/null 2>&1; then
        auth_ok="true"
        auth_user=$(glab api user --jq .username 2>/dev/null || true)
      fi
      ;;
    *) fail "preflight: invalid platform: $platform (expected github or gitlab)" 1 ;;
  esac

  # -- Branch --
  branch=$(git branch --show-current 2>/dev/null || true)

  # -- Uncommitted changes --
  if ! git diff --quiet 2>/dev/null; then
    has_uncommitted="true"
  fi
  if ! git diff --cached --quiet 2>/dev/null; then
    has_staged="true"
  fi
  if [[ -n "$(git ls-files --others --exclude-standard 2>/dev/null)" ]]; then
    has_untracked="true"
  fi

  # -- Output structured block --
  cat <<EOF
auth_ok=${auth_ok}
auth_user=${auth_user}
branch=${branch}
has_uncommitted=${has_uncommitted}
has_staged=${has_staged}
has_untracked=${has_untracked}
platform=${platform}
EOF
}

# ---------------------------------------------------------------------------
# Subcommand: push
# ---------------------------------------------------------------------------
# Push a branch to the specified remote with upstream tracking (-u).
#
# Flags:
#   --remote <name>    Git remote name (e.g., fork, origin)
#   --branch <branch>  Branch name to push

cmd_push() {
  local remote=""
  local branch=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --remote) flag_value "$1" "$#"; remote="$2"; shift 2 ;;
      --branch) flag_value "$1" "$#"; branch="$2"; shift 2 ;;
      *) fail "push: unknown flag: $1" 1 ;;
    esac
  done

  require_arg "--remote" "$remote"
  require_arg "--branch" "$branch"

  # Verify the remote exists
  if ! git remote get-url "$remote" >/dev/null 2>&1; then
    fail "push: remote '$remote' does not exist. Available remotes: $(git remote | tr '\n' ' ')" 3
  fi

  info "Pushing $branch to $remote..."
  if ! git push -u "$remote" "$branch" 2>&1; then
    fail "push: git push failed (remote=$remote, branch=$branch)" 3
  fi

  info "Push successful: $remote/$branch"
}

# ---------------------------------------------------------------------------
# Subcommand: check-existing
# ---------------------------------------------------------------------------
# Check whether an open PR (GitHub) or MR (GitLab) already exists for
# a branch.  Supports owner:branch format for fork-aware matching.
#
# Flags:
#   --repo <owner/repo>        Target repository
#   --head <ref>               Branch or owner:branch to match
#   --platform github|gitlab   Which platform (default: github)
#
# Exit code 0 if NO existing PR/MR found (safe to create one).
# Exit code 5 if an existing PR/MR IS found (details on stdout).

cmd_check_existing() {
  local repo=""
  local head=""
  local platform="github"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo) flag_value "$1" "$#"; repo="$2"; shift 2 ;;
      --head) flag_value "$1" "$#"; head="$2"; shift 2 ;;
      --platform) flag_value "$1" "$#"; platform="$2"; shift 2 ;;
      *) fail "check-existing: unknown flag: $1" 1 ;;
    esac
  done

  require_arg "--repo" "$repo"
  require_arg "--head" "$head"

  case "$platform" in
    github)
      local result exit_code=0
      if [[ "$head" == *:* ]]; then
        # owner:branch format — gh pr list --head does not support this
        # syntax.  Search by branch name and filter by head repo owner.
        local head_owner="${head%%:*}"
        local head_branch="${head#*:}"
        result=$(gh pr list --repo "$repo" --head "$head_branch" \
          --json number,url,headRepositoryOwner \
          --jq "[.[] | select(.headRepositoryOwner.login == \"$head_owner\")] | .[0] // empty" \
          2>/dev/null) || exit_code=$?
      else
        result=$(gh pr list --repo "$repo" --head "$head" \
          --json number,url --jq '.[0] // empty' 2>/dev/null) || exit_code=$?
      fi
      if [[ $exit_code -ne 0 ]]; then
        fail "check-existing: GitHub API query failed (exit $exit_code). Check gh auth status." 1
      fi
      if [[ -n "$result" ]]; then
        echo "$result"
        exit 5
      fi
      ;;
    gitlab)
      local source_branch="$head"
      local raw exit_code=0
      raw=$(glab mr list --repo "$repo" --source-branch "$source_branch" \
        --output json 2>/dev/null) || exit_code=$?
      if [[ $exit_code -ne 0 ]]; then
        fail "check-existing: GitLab API query failed (exit $exit_code). Check glab auth status." 1
      fi
      local result
      result=$(printf '%s' "$raw" | jq -r '.[0] // empty' 2>/dev/null)
      if [[ -n "$result" ]]; then
        echo "$result"
        exit 5
      fi
      ;;
    *) fail "check-existing: invalid platform: $platform" 1 ;;
  esac

  # No existing PR/MR found
  info "No existing PR/MR found for head=$head on $repo"
}

# ---------------------------------------------------------------------------
# Subcommand: create-pr
# ---------------------------------------------------------------------------
# Create a GitHub pull request via the gh CLI.
#
# Flags:
#   --repo <owner/repo>   Target repository (required for fork-based PRs)
#   --base <branch>       Base branch (e.g., main)
#   --head <ref>          Head ref — owner:branch for forks, branch for direct
#   --title <title>       PR title
#   --body-file <path>    Path to file containing PR body (mutually exclusive with --body)
#   --body <text>         Inline PR body text (mutually exclusive with --body-file)
#   --draft               Create as draft PR (default: true)
#   --no-draft            Create as non-draft PR
#   --labels <csv>        Comma-separated label names
#
# On success, prints the PR URL on stdout.

cmd_create_pr() {
  local repo=""
  local base=""
  local head=""
  local title=""
  local body_file=""
  local body=""
  local draft="true"
  local labels=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo) flag_value "$1" "$#"; repo="$2"; shift 2 ;;
      --base) flag_value "$1" "$#"; base="$2"; shift 2 ;;
      --head) flag_value "$1" "$#"; head="$2"; shift 2 ;;
      --title) flag_value "$1" "$#"; title="$2"; shift 2 ;;
      --body-file) flag_value "$1" "$#"; body_file="$2"; shift 2 ;;
      --body) flag_value "$1" "$#"; body="$2"; shift 2 ;;
      --draft) draft="true"; shift ;;
      --no-draft) draft="false"; shift ;;
      --labels) flag_value "$1" "$#"; labels="$2"; shift 2 ;;
      *) fail "create-pr: unknown flag: $1" 1 ;;
    esac
  done

  require_arg "--base" "$base"
  require_arg "--head" "$head"
  require_arg "--title" "$title"

  # Build gh pr create command
  local -a cmd=(gh pr create)

  if [[ "$draft" == "true" ]]; then
    cmd+=(--draft)
  fi

  if [[ -n "$repo" ]]; then
    cmd+=(--repo "$repo")
  fi

  cmd+=(--base "$base" --head "$head" --title "$title")

  if [[ -n "$body_file" ]]; then
    if [[ ! -f "$body_file" ]]; then
      fail "create-pr: body file not found: $body_file" 1
    fi
    cmd+=(--body-file "$body_file")
  elif [[ -n "$body" ]]; then
    cmd+=(--body "$body")
  else
    cmd+=(--body "")
  fi

  if [[ -n "$labels" ]]; then
    cmd+=(--label "$labels")
  fi

  info "Creating PR: ${title}"
  local pr_url
  local stderr_file
  stderr_file=$(mktemp)
  if pr_url=$("${cmd[@]}" 2>"$stderr_file"); then
    rm -f "$stderr_file"
    # gh pr create prints the URL on success
    echo "$pr_url"
    info "PR created: $pr_url"
  else
    # Print the error but use a distinct exit code so the skill can
    # detect the failure and fall back (e.g., to a compare URL).
    cat "$stderr_file" >&2
    rm -f "$stderr_file"
    exit 4
  fi
}

# ---------------------------------------------------------------------------
# Subcommand: create-mr
# ---------------------------------------------------------------------------
# Create a GitLab merge request via the glab CLI.
#
# Flags:
#   --project <path>      Upstream project path (for fork-based MRs)
#   --source <branch>     Source branch
#   --target <branch>     Target branch (e.g., main)
#   --title <title>       MR title
#   --description <text>  MR description text
#   --desc-file <path>    Path to file containing MR description
#   --draft               Create as draft MR (default: true)
#   --no-draft            Create as non-draft MR
#   --head <project>      Fork project path (for fork-based MRs)
#
# On success, prints the MR URL on stdout.

cmd_create_mr() {
  local project=""
  local source_branch=""
  local target_branch=""
  local title=""
  local description=""
  local desc_file=""
  local draft="true"
  local head_project=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project) flag_value "$1" "$#"; project="$2"; shift 2 ;;
      --source) flag_value "$1" "$#"; source_branch="$2"; shift 2 ;;
      --target) flag_value "$1" "$#"; target_branch="$2"; shift 2 ;;
      --title) flag_value "$1" "$#"; title="$2"; shift 2 ;;
      --description) flag_value "$1" "$#"; description="$2"; shift 2 ;;
      --desc-file) flag_value "$1" "$#"; desc_file="$2"; shift 2 ;;
      --draft) draft="true"; shift ;;
      --no-draft) draft="false"; shift ;;
      --head) flag_value "$1" "$#"; head_project="$2"; shift 2 ;;
      *) fail "create-mr: unknown flag: $1" 1 ;;
    esac
  done

  require_arg "--source" "$source_branch"
  require_arg "--target" "$target_branch"
  require_arg "--title" "$title"

  # Build glab mr create command
  local -a cmd=(glab mr create --yes)

  if [[ "$draft" == "true" ]]; then
    cmd+=(--draft)
  fi

  if [[ -n "$project" ]]; then
    cmd+=(--repo "$project")
  fi

  if [[ -n "$head_project" ]]; then
    cmd+=(--head "$head_project")
  fi

  cmd+=(--source-branch "$source_branch" --target-branch "$target_branch" --title "$title")

  if [[ -n "$desc_file" ]]; then
    if [[ ! -f "$desc_file" ]]; then
      fail "create-mr: description file not found: $desc_file" 1
    fi
    # glab uses --description, not --body-file — read the file content
    description=$(<"$desc_file")
  fi

  if [[ -n "$description" ]]; then
    cmd+=(--description "$description")
  fi

  info "Creating MR: ${title}"
  local mr_url
  local stderr_file
  stderr_file=$(mktemp)
  if mr_url=$("${cmd[@]}" 2>"$stderr_file"); then
    rm -f "$stderr_file"
    echo "$mr_url"
    info "MR created: $mr_url"
  else
    cat "$stderr_file" >&2
    rm -f "$stderr_file"
    exit 4
  fi
}

# ---------------------------------------------------------------------------
# Subcommand: save-metadata
# ---------------------------------------------------------------------------
# Write a JSON metadata file from key=value pairs with full escaping.
#
# Flags:
#   --file <path>   Output file path (required)
#
# Remaining positional arguments are key=value pairs. All values are
# stored as JSON strings to avoid leading-zero truncation and to keep
# the output type-stable.
#
# Example:
#   publish.sh save-metadata --file .artifacts/impl/EDM-1/publish-metadata.json \
#     repo=acme/project branch=feat/x base=main pr_number=42 \
#     pr_url=https://github.com/acme/project/pull/42 jira_key=EDM-1

cmd_save_metadata() {
  local file=""
  local -a pairs=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --file) flag_value "$1" "$#"; file="$2"; shift 2 ;;
      *=*) pairs+=("$1"); shift ;;
      *) fail "save-metadata: unexpected argument: $1 (expected key=value)" 1 ;;
    esac
  done

  require_arg "--file" "$file"

  if [[ ${#pairs[@]} -eq 0 ]]; then
    fail "save-metadata: no key=value pairs provided" 1
  fi

  # Build JSON using printf — avoids jq dependency.
  # Keys are sorted alphabetically for stable output.
  local json="{"
  local first="true"
  local -a sorted_pairs
  IFS=$'\n' read -r -d '' -a sorted_pairs < <(printf '%s\n' "${pairs[@]}" | sort && printf '\0') || true

  for pair in "${sorted_pairs[@]}"; do
    local key="${pair%%=*}"
    local value="${pair#*=}"

    if [[ "$first" == "true" ]]; then
      first="false"
    else
      json+=","
    fi

    # Always serialize as a JSON string to avoid leading-zero truncation
    # (e.g., "007" → 7) and to keep the output type-stable.  Full JSON
    # escaping handles newlines, tabs, quotes, backslashes, and control
    # characters that would otherwise produce invalid JSON.
    value=$(json_escape "$value")
    json+=$(printf '\n  "%s": "%s"' "$key" "$value")
  done

  json+=$'\n}\n'

  # Create parent directory if needed
  local dir
  dir=$(dirname "$file")
  if [[ ! -d "$dir" ]]; then
    mkdir -p "$dir"
  fi

  printf '%s' "$json" > "$file"
  info "Metadata saved to $file"
}

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
  usage
fi

subcommand="$1"
shift

case "$subcommand" in
  preflight)      cmd_preflight "$@" ;;
  push)           cmd_push "$@" ;;
  check-existing) cmd_check_existing "$@" ;;
  create-pr)      cmd_create_pr "$@" ;;
  create-mr)      cmd_create_mr "$@" ;;
  save-metadata)  cmd_save_metadata "$@" ;;
  -h|--help|help) usage ;;
  *) fail "Unknown subcommand: $subcommand. Run with --help for usage." 1 ;;
esac
