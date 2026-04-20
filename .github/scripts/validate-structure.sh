#!/usr/bin/env bash
# Structural validation for ai-workflows.
# Ensures documentation (AGENTS.md, README.md) stays in sync with the
# actual workflow directories and that every workflow follows the
# canonical file structure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

errors=0

fail() {
  echo "ERROR: $1"
  errors=$((errors + 1))
}

warn() {
  echo "WARN:  $1"
}

# ---------------------------------------------------------------------------
# 1. Discover workflows (any directory with a SKILL.md)
# ---------------------------------------------------------------------------
workflows=()
for skill in */SKILL.md; do
  [ -f "$skill" ] || continue
  workflows+=("$(dirname "$skill")")
done

if [ ${#workflows[@]} -eq 0 ]; then
  fail "No workflows discovered (no */SKILL.md found)"
  exit 1
fi

echo "Discovered workflows: ${workflows[*]}"
echo

# ---------------------------------------------------------------------------
# 2. Required files per workflow
# ---------------------------------------------------------------------------
echo "--- Required files ---"
for wf in "${workflows[@]}"; do
  for required in SKILL.md guidelines.md README.md; do
    if [ ! -f "$wf/$required" ]; then
      fail "$wf/ is missing required file: $required"
    fi
  done
done
echo

# ---------------------------------------------------------------------------
# 3. SKILL.md frontmatter validation
# ---------------------------------------------------------------------------
echo "--- SKILL.md frontmatter ---"
for wf in "${workflows[@]}"; do
  skill="$wf/SKILL.md"
  if ! head -1 "$skill" | grep -q '^---$'; then
    fail "$skill: missing YAML frontmatter (no opening ---)"
    continue
  fi

  fm=$(sed -n '2,/^---$/p' "$skill" | head -n -1)

  if ! echo "$fm" | grep -q '^name:'; then
    fail "$skill: frontmatter missing 'name' field"
  fi
  if ! echo "$fm" | grep -q '^description:'; then
    fail "$skill: frontmatter missing 'description' field"
  fi
done
echo

# ---------------------------------------------------------------------------
# 4. commands/ frontmatter — colon-namespaced name field
# ---------------------------------------------------------------------------
echo "--- commands/ frontmatter ---"
for wf in "${workflows[@]}"; do
  [ -d "$wf/commands" ] || continue
  for cmd in "$wf"/commands/*.md; do
    [ -f "$cmd" ] || continue
    if ! head -1 "$cmd" | grep -q '^---$'; then
      fail "$cmd: missing YAML frontmatter"
      continue
    fi

    name_line=$(sed -n '2,/^---$/p' "$cmd" | grep '^name:' || true)
    if [ -z "$name_line" ]; then
      fail "$cmd: frontmatter missing 'name' field"
      continue
    fi

    name_val=$(echo "$name_line" | sed 's/^name: *//; s/^"//; s/"$//')
    if ! echo "$name_val" | grep -q "^${wf}:"; then
      fail "$cmd: name '$name_val' does not follow colon notation '${wf}:<command>'"
    fi
  done
done
echo

# ---------------------------------------------------------------------------
# 5. AGENTS.md cross-checks
# ---------------------------------------------------------------------------
echo "--- AGENTS.md cross-checks ---"
agents="AGENTS.md"

for wf in "${workflows[@]}"; do
  # 5a. Workflow list (lines like: - **workflow** — ...)
  if ! grep -qF -- "- **${wf}**" "$agents"; then
    fail "AGENTS.md: workflow list missing entry for '$wf'"
  fi

  # 5b. Artifact management (lines like: - **workflow**: `.artifacts/...)
  if ! grep -qF -- "- **${wf}**:" "$agents"; then
    fail "AGENTS.md: artifact management missing entry for '$wf'"
  fi

  # 5c. Workflow-Specific Notes (### heading)
  if ! grep -qF -- "### ${wf}" "$agents"; then
    fail "AGENTS.md: workflow-specific notes missing '### $wf' section"
  fi

  # 5d. File organization tree (line containing the workflow dir name)
  if ! sed -n '/^```text/,/^```/p' "$agents" | grep -qF -- "${wf}/"; then
    fail "AGENTS.md: file organization tree missing '$wf/'"
  fi
done
echo

# ---------------------------------------------------------------------------
# 6. Root README.md cross-checks
# ---------------------------------------------------------------------------
echo "--- README.md cross-checks ---"
readme="README.md"

for wf in "${workflows[@]}"; do
  wf_title=$(echo "$wf" | sed 's/-/ /g')
  if ! grep -qi "\*\*${wf}\*\*\|${wf_title}" "$readme"; then
    fail "README.md: missing entry for workflow '$wf'"
  fi
done
echo

# ---------------------------------------------------------------------------
# 7. No absolute paths in skill files
# ---------------------------------------------------------------------------
echo "--- Absolute path check ---"
for wf in "${workflows[@]}"; do
  while IFS= read -r -d '' f; do
    # Skip paths inside fenced code blocks that look like examples (e.g. /home/user/)
    if grep -nE '/(home|Users|tmp|var)/' "$f" \
        | grep -vE '/(home/user|Users/name|Users/me)/' \
        | grep -vE '(e\.g\.|example|placeholder)' \
        > /dev/null 2>&1; then
      matches=$(grep -nE '/(home|Users|tmp|var)/' "$f" \
        | grep -vE '/(home/user|Users/name|Users/me)/' \
        | grep -vE '(e\.g\.|example|placeholder)')
      while IFS= read -r match; do
        fail "$f: contains absolute path: $match"
      done <<< "$matches"
    fi
  done < <(find "$wf" -name '*.md' -print0)
done
echo

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "==========================="
if [ "$errors" -gt 0 ]; then
  echo "FAILED: $errors error(s) found"
  exit 1
else
  echo "PASSED: all structural checks OK"
  exit 0
fi
