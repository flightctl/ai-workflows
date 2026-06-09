#!/usr/bin/env bash
# Validates that workflow versions are bumped when behavioral files change.
# Run in CI via .github/workflows/lint.yaml.
#
# On PRs: compares the branch against the merge base with the target branch.
# On push to main: compares HEAD against its first parent (handles merge commits).
# Locally: compares against origin/main.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

errors=0
warnings=0

fail() {
  echo "FAIL: $1"
  errors=$((errors + 1))
}

warn() {
  echo "WARN: $1"
  warnings=$((warnings + 1))
}

info() {
  echo "INFO: $1"
}

# ---------------------------------------------------------------------------
# 1. Determine base ref
# ---------------------------------------------------------------------------
if [ -n "${GITHUB_BASE_REF:-}" ]; then
  BASE_REF="origin/${GITHUB_BASE_REF}"
elif [ "${GITHUB_EVENT_NAME:-}" = "push" ]; then
  BASE_REF=$(git rev-parse HEAD^1)
else
  BASE_REF="origin/main"
fi

MERGE_BASE=$(git merge-base "$BASE_REF" HEAD 2>/dev/null || echo "$BASE_REF")
info "Base ref: $BASE_REF"
info "Merge base: $MERGE_BASE"

# ---------------------------------------------------------------------------
# 2. Get changed files
# ---------------------------------------------------------------------------
mapfile -t CHANGED_FILES < <(git diff --name-only "$MERGE_BASE"...HEAD 2>/dev/null \
  || git diff --name-only "$MERGE_BASE" HEAD)

if [ ${#CHANGED_FILES[@]} -eq 0 ]; then
  info "No changed files detected"
  exit 0
fi

# ---------------------------------------------------------------------------
# 3. Semver comparison: returns 0 if $1 < $2
# ---------------------------------------------------------------------------
semver_lt() {
  local IFS='.'
  read -r a1 a2 a3 <<< "$1"
  read -r b1 b2 b3 <<< "$2"
  if [ "$a1" -lt "$b1" ]; then return 0; fi
  if [ "$a1" -gt "$b1" ]; then return 1; fi
  if [ "$a2" -lt "$b2" ]; then return 0; fi
  if [ "$a2" -gt "$b2" ]; then return 1; fi
  if [ "$a3" -lt "$b3" ]; then return 0; fi
  return 1
}

# ---------------------------------------------------------------------------
# 4. Behavioral file detection
# ---------------------------------------------------------------------------
is_behavioral() {
  local file="$1"
  case "$file" in
    */skills/*.md|*/commands/*.md|*/guidelines.md)
      return 0 ;;
    */templates/*|*/prompts/*|*/scripts/*)
      return 0 ;;
    _shared/*.md|_shared/**/*.md)
      return 0 ;;
    */SKILL.md)
      local body_diff
      body_diff=$(git diff "$MERGE_BASE"...HEAD -- "$file" 2>/dev/null \
        || git diff "$MERGE_BASE" HEAD -- "$file")
      body_diff=$(echo "$body_diff" \
        | grep '^[+-]' \
        | grep -v '^[+-]version:' \
        | grep -v '^[+-]---' \
        | grep -v '^[+-][+-][+-]' || true)
      [ -n "$body_diff" ] && return 0
      return 1 ;;
    */README.md|*/GUIDE.md)
      return 1 ;;
    */*)
      local dir
      dir=$(dirname "$file")
      if [ -f "$dir/SKILL.md" ] && [[ "$file" == *.md ]]; then
        return 0
      fi
      return 1 ;;
    *)
      return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# 5. Detect behavioral changes and version bumps per workflow
# ---------------------------------------------------------------------------
declare -A workflow_behavioral_changed
declare -A workflow_version_bumped
declare -A shared_changed

for file in "${CHANGED_FILES[@]}"; do
  if [[ "$file" == _shared/* ]]; then
    if is_behavioral "$file"; then
      shared_changed["$file"]=1
    fi
    continue
  fi

  wf="${file%%/*}"
  [ -f "$wf/SKILL.md" ] || continue

  if is_behavioral "$file"; then
    workflow_behavioral_changed["$wf"]=1
  fi

  if [ "$file" = "$wf/SKILL.md" ]; then
    new_ver=$(sed -n 's/^version: *//p' "$wf/SKILL.md")
    old_ver=$(git show "$MERGE_BASE:$wf/SKILL.md" 2>/dev/null \
      | sed -n 's/^version: *//p' || echo "")
    if [ -n "$new_ver" ] && [ -n "$old_ver" ] && [ "$new_ver" != "$old_ver" ]; then
      workflow_version_bumped["$wf"]=1
    elif [ -n "$new_ver" ] && [ -z "$old_ver" ]; then
      workflow_version_bumped["$wf"]=1
    fi
  fi
done

# ---------------------------------------------------------------------------
# 6. Workflows with behavioral changes must have version bumps
# ---------------------------------------------------------------------------
for wf in "${!workflow_behavioral_changed[@]}"; do
  if [ -z "${workflow_version_bumped[$wf]:-}" ]; then
    fail "$wf: behavioral files changed but version not bumped in SKILL.md"
  else
    new_ver=$(sed -n 's/^version: *//p' "$wf/SKILL.md")
    old_ver=$(git show "$MERGE_BASE:$wf/SKILL.md" 2>/dev/null \
      | sed -n 's/^version: *//p' || echo "")
    if [ -n "$old_ver" ] && [ -n "$new_ver" ]; then
      if ! semver_lt "$old_ver" "$new_ver"; then
        fail "$wf: version $new_ver is not greater than $old_ver"
      fi
    fi
  fi
done

# ---------------------------------------------------------------------------
# 7. Advisory: signals that suggest MAJOR bump
# ---------------------------------------------------------------------------
for file in "${CHANGED_FILES[@]}"; do
  wf="${file%%/*}"
  [ -f "$wf/SKILL.md" ] || continue

  if ! [ -f "$file" ] && git show "$MERGE_BASE:$file" >/dev/null 2>&1; then
    case "$file" in
      */skills/*.md|*/commands/*.md)
        warn "$wf: deleted $file — consider MAJOR version bump" ;;
    esac
  fi
done

# ---------------------------------------------------------------------------
# 8. Cascade: shared file changes require consuming workflow bumps
# ---------------------------------------------------------------------------
for shared_file in "${!shared_changed[@]}"; do
  base=$(basename "$shared_file" .md)

  referencing_workflows=""

  # Direct references in standard behavioral locations
  direct=$(grep -rl "$base" */skills/*.md */commands/*.md */guidelines.md \
    2>/dev/null | sed 's|/.*||' | sort -u || true)
  if [ -n "$direct" ]; then
    referencing_workflows="$direct"
  fi

  # Also check root-level workflow .md files (e.g., design/decomposition-review.md)
  for wf_dir in */; do
    wf="${wf_dir%/}"
    [ -f "$wf/SKILL.md" ] || continue
    for root_md in "$wf"/*.md; do
      [ -f "$root_md" ] || continue
      case "$(basename "$root_md")" in
        SKILL.md|README.md|GUIDE.md|guidelines.md) continue ;;
      esac
      if grep -q "$base" "$root_md" 2>/dev/null; then
        referencing_workflows=$(printf '%s\n%s' "$referencing_workflows" "$wf" | sort -u)
      fi
    done
  done

  for wf in $referencing_workflows; do
    [ -n "$wf" ] || continue
    [ -f "$wf/SKILL.md" ] || continue
    if [ -z "${workflow_version_bumped[$wf]:-}" ]; then
      fail "$wf: references changed shared file $shared_file but version not bumped"
    fi
  done

  # Transitive: shared file A references shared file B
  transitive_shared=$(find _shared -name '*.md' -exec grep -l "$base" {} \; 2>/dev/null || true)
  for trans in $transitive_shared; do
    [ "$trans" = "$shared_file" ] && continue
    trans_base=$(basename "$trans" .md)
    trans_workflows=$(grep -rl "$trans_base" */skills/*.md */commands/*.md \
      */guidelines.md 2>/dev/null | sed 's|/.*||' | sort -u || true)
    for tw in $trans_workflows; do
      [ -f "$tw/SKILL.md" ] || continue
      if [ -z "${workflow_version_bumped[$tw]:-}" ]; then
        fail "$tw: transitively affected by $shared_file (via $trans) but version not bumped"
      fi
    done
  done
done

# ---------------------------------------------------------------------------
# 9. Static: all SKILL.md files must have valid semver
# ---------------------------------------------------------------------------
for skill in */SKILL.md; do
  [ -f "$skill" ] || continue
  wf=$(dirname "$skill")
  ver=$(sed -n 's/^version: *//p' "$skill")
  if [ -z "$ver" ]; then
    fail "$wf: SKILL.md missing version field"
  elif ! echo "$ver" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    fail "$wf: version '$ver' is not valid semver (expected X.Y.Z)"
  fi
done

# ---------------------------------------------------------------------------
# 10. Static: all _shared/*.md files must have valid frontmatter with version
# ---------------------------------------------------------------------------
while IFS= read -r -d '' shared; do
  if ! head -1 "$shared" | grep -q '^---$'; then
    fail "$shared: missing YAML frontmatter"
    continue
  fi
  fm=$(sed -n '2,/^---$/p' "$shared" | head -n -1)
  if ! echo "$fm" | grep -q '^version:'; then
    fail "$shared: frontmatter missing version field"
  else
    ver=$(echo "$fm" | grep '^version:' | sed 's/^version: *//')
    if ! echo "$ver" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
      fail "$shared: version '$ver' is not valid semver"
    fi
  fi
done < <(find _shared -name '*.md' -print0 2>/dev/null)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "==========================="
if [ "$errors" -gt 0 ]; then
  echo "FAILED: $errors error(s), $warnings warning(s)"
  exit 1
else
  echo "PASSED: $warnings warning(s), no errors"
  exit 0
fi
