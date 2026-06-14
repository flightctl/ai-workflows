package harness

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// artifactPath returns the path to an artifact file produced by the implement skill.
func artifactPath(projectDir, storyKey, filename string) string {
	return filepath.Join(projectDir, ".artifacts", "implement", storyKey, filename)
}

// readArtifact reads an artifact file, failing the test if it doesn't exist.
func readArtifact(t T, projectDir, storyKey, filename string) string {
	t.Helper()
	path := artifactPath(projectDir, storyKey, filename)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("artifact %s not found at %s: %v", filename, path, err)
	}
	return string(data)
}

// containsSections returns the first missing section heading, or "" if all are present.
func containsSections(content string, sections []string) string {
	for _, s := range sections {
		if !strings.Contains(content, s) {
			return s
		}
	}
	return ""
}

// AssertIngest validates the 01-context.md produced by the /ingest phase.
func AssertIngest(t T, projectDir string, s Scenario) {
	t.Helper()
	content := readArtifact(t, projectDir, s.StoryKey, "01-context.md")

	if missing := containsSections(content, s.Assertions.Ingest.RequiredSections); missing != "" {
		t.Errorf("01-context.md missing section: %q", missing)
	}

	for _, item := range s.Assertions.Ingest.ValidationProfileContains {
		if !strings.Contains(content, item) {
			t.Errorf("01-context.md validation profile missing: %q", item)
		}
	}

	if pat := s.Assertions.Ingest.BranchPattern; pat != "" {
		re, err := regexp.Compile(strings.ReplaceAll(pat, "*", ".*"))
		if err != nil {
			t.Fatalf("invalid BranchPattern %q: %v", pat, err)
		}
		if !re.MatchString(content) {
			t.Errorf("01-context.md does not contain branch matching %q", pat)
		}
	}
}

// AssertPlan validates the 02-plan.md produced by the /plan phase.
func AssertPlan(t T, projectDir string, s Scenario) {
	t.Helper()
	content := readArtifact(t, projectDir, s.StoryKey, "02-plan.md")

	if missing := containsSections(content, s.Assertions.Plan.RequiredSections); missing != "" {
		t.Errorf("02-plan.md missing section: %q", missing)
	}

	for _, item := range s.Assertions.Plan.MustMention {
		if !strings.Contains(content, item) {
			t.Errorf("02-plan.md does not mention: %q", item)
		}
	}

	if min := s.Assertions.Plan.MinTasks; min > 0 {
		// Match any level-3 or level-4 heading that starts with "Task"
		// e.g. "### Task 1:", "#### Task 1:", "### Task: description"
		taskHeading := regexp.MustCompile(`(?m)^#{3,4} Task`)
		count := len(taskHeading.FindAllString(content, -1))
		if count < min {
			t.Errorf("02-plan.md has %d tasks (### Task or #### Task headings), want at least %d", count, min)
		}
	}
}

// AssertCode validates that the /code phase produced the expected files and commits.
func AssertCode(t T, projectDir string, s Scenario) {
	t.Helper()

	for _, f := range s.Assertions.Code.NewFiles {
		full := filepath.Join(projectDir, f)
		if _, err := os.Stat(full); os.IsNotExist(err) {
			t.Errorf("expected new file not found: %s", f)
		}
	}

	if min := s.Assertions.Code.MinCommits; min > 0 {
		out, err := exec.Command("git", "-C", projectDir, "log", "--oneline").Output()
		if err != nil {
			t.Fatalf("git log: %v", err)
		}
		count := strings.Count(strings.TrimSpace(string(out)), "\n") + 1
		if count < min {
			t.Errorf("git log has %d commits, want at least %d", count, min)
		}
	}

	if min := s.Assertions.Code.MinTestFunctions; min > 0 {
		total := 0
		for _, f := range s.Assertions.Code.NewFiles {
			if !strings.HasSuffix(f, "_test.go") {
				continue
			}
			data, err := os.ReadFile(filepath.Join(projectDir, f))
			if err != nil {
				continue
			}
			total += strings.Count(string(data), "\nfunc Test")
		}
		if total < min {
			t.Errorf("test files have %d Test* functions, want at least %d", total, min)
		}
	}
}

// AssertValidate checks the 05-validation-report.md verdict.
func AssertValidate(t T, projectDir string, s Scenario) {
	t.Helper()
	content := readArtifact(t, projectDir, s.StoryKey, "05-validation-report.md")

	verdict := s.Assertions.Validate.ExpectedVerdict
	if verdict != "" && !strings.Contains(strings.ToUpper(content), strings.ToUpper(verdict)) {
		t.Errorf("05-validation-report.md does not contain expected verdict %q", verdict)
	}
}

// AssertPublish checks that mock gh recorded a pr-record.json with the expected fields.
func AssertPublish(t T, projectDir string, s Scenario) {
	t.Helper()
	recordPath := filepath.Join(projectDir, "pr-record.json")
	data, err := os.ReadFile(recordPath)
	if err != nil {
		t.Fatalf("pr-record.json not found: %v", err)
	}

	var record map[string]string
	if err := json.Unmarshal(data, &record); err != nil {
		t.Fatalf("parse pr-record.json: %v", err)
	}

	if title := s.Assertions.Publish.TitleContains; title != "" {
		if !strings.Contains(record["title"], title) {
			t.Errorf("PR title %q does not contain %q", record["title"], title)
		}
	}

	if base := s.Assertions.Publish.BaseBranch; base != "" {
		if record["base"] != base {
			t.Errorf("PR base branch %q, want %q", record["base"], base)
		}
	}
}

// AssertBuildPasses runs the compile command inside the fixture container
// and fails the test if it exits non-zero.
func AssertBuildPasses(t T, fc *FixtureContainer, s Scenario) {
	t.Helper()
	if s.Build.Compile == "" {
		return
	}
	fc.Exec(t, s.Build.Compile)
}

// AssertTestsPassed runs the project's own test suite inside the fixture
// container and fails on non-zero exit.
func AssertTestsPassed(t T, fc *FixtureContainer, s Scenario) {
	t.Helper()
	if s.Build.Test == "" {
		return
	}
	fc.Exec(t, s.Build.Test)
}

// AssertCoverage measures coverage of the new implementation files the agent
// created, derived from s.Assertions.Code.NewFiles.
//
// It runs `go test -coverprofile` against the packages that contain the new
// files, then parses per-function coverage lines and averages the result across
// all functions in those files. This isolates the agent's new code from
// pre-existing uncovered code in the same packages.
//
// Returns early (no failure) if CoverageThreshold is 0 or NewFiles is empty.
func AssertCoverage(t T, fc *FixtureContainer, projectDir string, s Scenario) {
	t.Helper()
	if s.Build.CoverageThreshold == 0 || len(s.Assertions.Code.NewFiles) == 0 {
		return
	}

	// Derive unique package dirs and new implementation file basenames from NewFiles.
	pkgSet := map[string]bool{}
	newImplFiles := map[string]bool{}
	for _, f := range s.Assertions.Code.NewFiles {
		if strings.HasSuffix(f, "_test.go") {
			continue
		}
		newImplFiles[filepath.Base(f)] = true
		pkgSet["./"+filepath.Dir(f)] = true
	}
	if len(pkgSet) == 0 {
		return
	}

	pkgs := make([]string, 0, len(pkgSet))
	for pkg := range pkgSet {
		pkgs = append(pkgs, pkg)
	}
	sort.Strings(pkgs)

	coverCmd := fmt.Sprintf(
		"go test -coverprofile=/tmp/coverage.out %s && go tool cover -func=/tmp/coverage.out",
		strings.Join(pkgs, " "),
	)
	out := fc.Exec(t, coverCmd)

	// Parse per-function lines: "<pkg>/file.go:line:  FuncName  80.0%"
	funcLine := regexp.MustCompile(`([^/\s]+\.go):\d+:\s+\S+\s+([\d.]+)%`)
	var total, count float64
	for _, line := range strings.Split(out, "\n") {
		m := funcLine.FindStringSubmatch(line)
		if m == nil || !newImplFiles[m[1]] {
			continue
		}
		var pct float64
		fmt.Sscanf(m[2], "%f", &pct)
		total += pct
		count++
	}
	if count == 0 {
		t.Logf("WARNING: no per-function coverage found for %v in output; skipping", newImplFiles)
		return
	}
	avg := total / count
	t.Logf("new-file coverage: %.1f%% avg over %d functions in %v", avg, int(count), newImplFiles)
	if int(avg) < s.Build.CoverageThreshold {
		t.Errorf("new-file coverage %.1f%% below threshold %d%%", avg, s.Build.CoverageThreshold)
	}
}
