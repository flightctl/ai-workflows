#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_ROOT="$(mktemp -d)"
TEST_HOME="${TEST_ROOT}/home"
TEST_PROJECT="${TEST_ROOT}/project"
trap 'rm -rf "$TEST_ROOT"' EXIT

mkdir -p "$TEST_HOME" "$TEST_PROJECT"

HOME="$TEST_HOME" "$REPO_ROOT/install.sh" codex \
  --packages bugfix,report-bug --no-update-timer

for package in bugfix report-bug; do
  test -L "${TEST_HOME}/.agents/skills/${package}"
done
test -L "${TEST_HOME}/.agents/skills/_shared"

HOME="$TEST_HOME" "$REPO_ROOT/uninstall.sh" codex --packages report-bug
test ! -e "${TEST_HOME}/.agents/skills/report-bug"
test -L "${TEST_HOME}/.agents/skills/bugfix"
test -L "${TEST_HOME}/.agents/skills/_shared"

HOME="$TEST_HOME" "$REPO_ROOT/uninstall.sh" codex --packages bugfix
test ! -e "${TEST_HOME}/.agents/skills/bugfix"
test ! -e "${TEST_HOME}/.agents/skills/_shared"

HOME="$TEST_HOME" "$REPO_ROOT/install.sh" all --project "$TEST_PROJECT" \
  --packages report-bug --no-update-timer
test -L "${TEST_PROJECT}/.agents/skills/report-bug"
test -L "${TEST_PROJECT}/.agents/skills/_shared"

HOME="$TEST_HOME" "$REPO_ROOT/uninstall.sh" all --project "$TEST_PROJECT" \
  --packages report-bug
test ! -e "${TEST_PROJECT}/.agents/skills/report-bug"
test ! -e "${TEST_PROJECT}/.agents/skills/_shared"
