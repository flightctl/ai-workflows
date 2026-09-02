#!/usr/bin/env bash
# Validates that package versions are bumped when behavioral files change.
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

# Find workflow and simple-skill packages that reference a shared-file basename
# in behavioral files, including workflow entry points and root-level workflow
# .md files (e.g., design/decomposition-review.md).
find_packages_referencing() {
  local base="$1"
  local packages=""

  local from_grep
  from_grep=$(grep -rl "$base" \
    -- \
    */SKILL.md \
    */guidelines.md \
    */skills/*.md \
    */commands/*.md \
    */templates/*.md \
    */prompts/*.md \
    */scripts/* \
    2>/dev/null | sed 's|/.*||' | sort -u || true)
  if [ -n "$from_grep" ]; then
    packages="$from_grep"
  fi

  local from_simple_skills
  from_simple_skills=$(grep -rl "$base" \
    -- \
    skills/*/SKILL.md \
    skills/*/references/*.md \
    skills/*/templates/* \
    skills/*/prompts/*.md \
    skills/*/scripts/* \
    2>/dev/null | sed -E 's|^(skills/[^/]+)/.*|\1|' | sort -u || true)
  if [ -n "$from_simple_skills" ]; then
    packages=$(printf '%s\n%s' "$packages" "$from_simple_skills" | sort -u)
  fi

  for package_dir in */; do
    package="${package_dir%/}"
    [ -f "$package/SKILL.md" ] || continue
    for root_md in "$package"/*.md; do
      [ -f "$root_md" ] || continue
      case "$(basename "$root_md")" in
        SKILL.md|README.md|GUIDE.md|guidelines.md) continue ;;
      esac
      if grep -q "$base" "$root_md" 2>/dev/null; then
        packages=$(printf '%s\n%s' "$packages" "$package" | sort -u)
      fi
    done
  done

  printf '%s\n' "$packages" | sed '/^$/d'
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
    */skills/*.md|*/commands/*.md|*/guidelines.md|skills/*/references/*)
      return 0 ;;
    */templates/*|*/prompts/*|*/scripts/*)
      return 0 ;;
    _shared/*.md|_shared/*/*.md)
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
# 5. Static: all SKILL.md files must have valid semver
# ---------------------------------------------------------------------------
package_names=()
for skill in */SKILL.md skills/*/SKILL.md; do
  [ -f "$skill" ] || continue
  package=$(dirname "$skill")
  package_name=$(basename "$package")
  for existing_name in "${package_names[@]}"; do
    if [ "$existing_name" = "$package_name" ]; then
      fail "duplicate package name '$package_name'"
    fi
  done
  package_names+=("$package_name")
  ver=$(sed -n 's/^version: *//p' "$skill")
  if [ -z "$ver" ]; then
    fail "$package: SKILL.md missing version field"
  elif ! echo "$ver" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    fail "$package: version '$ver' is not valid semver (expected X.Y.Z)"
  fi
done

# ---------------------------------------------------------------------------
# 6. Static: all _shared/*.md files must have valid frontmatter with version
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
# 7. Detect behavioral changes and version bumps per package
# ---------------------------------------------------------------------------
declare -A package_behavioral_changed
declare -A package_version_bumped
declare -A shared_changed

for file in "${CHANGED_FILES[@]}"; do
  if [[ "$file" == _shared/* ]]; then
    if is_behavioral "$file"; then
      shared_changed["$file"]=1
    fi
    continue
  fi

  package="${file%%/*}"
  if [[ "$file" == skills/*/* ]]; then
    skill_rest="${file#skills/}"
    candidate="skills/${skill_rest%%/*}"
    [ -f "$candidate/SKILL.md" ] && package="$candidate"
  fi
  [ -f "$package/SKILL.md" ] || continue

  if is_behavioral "$file"; then
    package_behavioral_changed["$package"]=1
  fi

  if [ "$file" = "$package/SKILL.md" ]; then
    new_ver=$(sed -n 's/^version: *//p' "$package/SKILL.md")
    old_ver=$(git show "$MERGE_BASE:$package/SKILL.md" 2>/dev/null \
      | sed -n 's/^version: *//p' || echo "")
    if [ -n "$new_ver" ] && [ -n "$old_ver" ] && [ "$new_ver" != "$old_ver" ]; then
      package_version_bumped["$package"]=1
    elif [ -n "$new_ver" ] && [ -z "$old_ver" ]; then
      package_version_bumped["$package"]=1
    fi
  fi
done

# ---------------------------------------------------------------------------
# 8. Packages with behavioral changes must have version bumps
# ---------------------------------------------------------------------------
for package in "${!package_behavioral_changed[@]}"; do
  if [ -z "${package_version_bumped[$package]:-}" ]; then
    fail "$package: behavioral files changed but version not bumped in SKILL.md"
  else
    new_ver=$(sed -n 's/^version: *//p' "$package/SKILL.md")
    old_ver=$(git show "$MERGE_BASE:$package/SKILL.md" 2>/dev/null \
      | sed -n 's/^version: *//p' || echo "")
    if [ -n "$old_ver" ] && [ -n "$new_ver" ]; then
      if ! semver_lt "$old_ver" "$new_ver"; then
        fail "$package: version $new_ver is not greater than $old_ver"
      fi
    fi
  fi
done

# ---------------------------------------------------------------------------
# 9. Advisory: signals that suggest MAJOR bump
# ---------------------------------------------------------------------------
for file in "${CHANGED_FILES[@]}"; do
  package="${file%%/*}"
  if [[ "$file" == skills/*/* ]]; then
    skill_rest="${file#skills/}"
    candidate="skills/${skill_rest%%/*}"
    [ -f "$candidate/SKILL.md" ] && package="$candidate"
  fi
  [ -f "$package/SKILL.md" ] || continue

  if ! [ -f "$file" ] && git show "$MERGE_BASE:$file" >/dev/null 2>&1; then
    case "$file" in
      */skills/*.md|*/commands/*.md)
        warn "$package: deleted $file — consider MAJOR version bump" ;;
    esac
  fi
done

# ---------------------------------------------------------------------------
# 10. Shared files themselves must have version bumps when changed
# ---------------------------------------------------------------------------
for shared_file in "${!shared_changed[@]}"; do
  new_ver=$(sed -n 's/^version: *//p' "$shared_file")
  old_ver=$(git show "$MERGE_BASE:$shared_file" 2>/dev/null \
    | sed -n 's/^version: *//p' || echo "")
  if [ -n "$new_ver" ] && [ -n "$old_ver" ] && [ "$new_ver" = "$old_ver" ]; then
    fail "$shared_file: behavioral content changed but version not bumped (still $old_ver)"
  elif [ -n "$old_ver" ] && [ -n "$new_ver" ] && [ "$new_ver" != "$old_ver" ]; then
    if ! semver_lt "$old_ver" "$new_ver"; then
      fail "$shared_file: version $new_ver is not greater than $old_ver"
    fi
  fi
done

# ---------------------------------------------------------------------------
# 11. Cascade: shared file changes require consuming package bumps
# ---------------------------------------------------------------------------
for shared_file in "${!shared_changed[@]}"; do
  base=$(basename "$shared_file" .md)

  referencing_packages=""

  referencing_packages=$(find_packages_referencing "$base")

  for package in $referencing_packages; do
    [ -n "$package" ] || continue
    [ -f "$package/SKILL.md" ] || continue
    if [ -z "${package_version_bumped[$package]:-}" ]; then
      fail "$package: references changed shared file $shared_file but version not bumped"
    fi
  done

  # Transitive: shared file A references shared file B
  transitive_shared=$(find _shared -name '*.md' -exec grep -l "$base" {} \; 2>/dev/null || true)
  for trans in $transitive_shared; do
    [ "$trans" = "$shared_file" ] && continue
    trans_base=$(basename "$trans" .md)
    transitive_packages=$(find_packages_referencing "$trans_base")
    for package in $transitive_packages; do
      [ -f "$package/SKILL.md" ] || continue
      if [ -z "${package_version_bumped[$package]:-}" ]; then
        fail "$package: transitively affected by $shared_file (via $trans) but version not bumped"
      fi
    done
  done
done

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
