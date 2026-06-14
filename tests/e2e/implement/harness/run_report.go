package harness

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// RunReport captures the full metrics for one e2e run of a scenario.
// It is appended as a single JSON line to .artifacts/e2e-reports/{ID}-runs.jsonl
// so that historical runs accumulate and can be graphed later.
type RunReport struct {
	Timestamp   string                 `json:"ts"`
	WorkflowSHA string                 `json:"workflow_sha,omitempty"`
	ScenarioID  string                 `json:"scenario_id"`
	Phases      map[string]PhaseRecord `json:"phases"`
	Quality     *QualityRecord         `json:"quality,omitempty"`
}

// PhaseRecord holds token and timing data for a single claude CLI invocation.
type PhaseRecord struct {
	InputTokens  int     `json:"input_tokens"`
	OutputTokens int     `json:"output_tokens"`
	CacheRead    int     `json:"cache_read_input_tokens"`
	CacheWrite   int     `json:"cache_creation_input_tokens"`
	TotalTokens  int     `json:"total_tokens"`
	DurationSec  float64 `json:"duration_sec"`
}

// QualityRecord mirrors the scored fields from ComparisonReport.
type QualityRecord struct {
	Verdict       string `json:"verdict"`
	Correctness   int    `json:"correctness"`
	Readability   int    `json:"readability"`
	TestCoverage  int    `json:"test_coverage"`
	ErrorHandling int    `json:"error_handling"`
	Summary       string `json:"summary,omitempty"`
}

// NewRunReport creates an empty RunReport for the given scenario, stamped with
// the current time and the HEAD commit of the ai-workflows repo.
func NewRunReport(s Scenario) *RunReport {
	return &RunReport{
		Timestamp:   time.Now().UTC().Format(time.RFC3339),
		WorkflowSHA: workflowGitSHA(),
		ScenarioID:  s.ID,
		Phases:      make(map[string]PhaseRecord),
	}
}

// RecordPhase stores the token usage and duration from a RunResult into the report.
func (r *RunReport) RecordPhase(phase string, result RunResult) {
	u := result.TokensUsed
	r.Phases[phase] = PhaseRecord{
		InputTokens:  u.InputTokens,
		OutputTokens: u.OutputTokens,
		CacheRead:    u.CacheRead,
		CacheWrite:   u.CacheWrite,
		TotalTokens:  u.InputTokens + u.OutputTokens,
		DurationSec:  result.Duration.Seconds(),
	}
}

// RecordQuality embeds quality scores from a ComparisonReport.
func (r *RunReport) RecordQuality(c *ComparisonReport) {
	if c == nil {
		return
	}
	r.Quality = &QualityRecord{
		Verdict:       c.Verdict,
		Correctness:   c.Correctness,
		Readability:   c.Readability,
		TestCoverage:  c.TestCoverage,
		ErrorHandling: c.ErrorHandling,
		Summary:       c.Summary,
	}
}

// Write appends the report as a single JSON line to
// .artifacts/e2e-reports/{ScenarioID}-runs.jsonl inside projectDir.
// Failures are logged as warnings — never fail the test.
func (r *RunReport) Write(t T, projectDir string) {
	t.Helper()

	outDir := filepath.Join(projectDir, ".artifacts", "e2e-reports")
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		t.Logf("WARNING: run report: mkdir %s: %v", outDir, err)
		return
	}

	line, err := json.Marshal(r)
	if err != nil {
		t.Logf("WARNING: run report: marshal: %v", err)
		return
	}

	path := filepath.Join(outDir, r.ScenarioID+"-runs.jsonl")
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		t.Logf("WARNING: run report: open %s: %v", path, err)
		return
	}
	defer f.Close()

	if _, err := fmt.Fprintf(f, "%s\n", line); err != nil {
		t.Logf("WARNING: run report: write %s: %v", path, err)
		return
	}

	t.Logf("run report appended: %s", path)
}

// workflowGitSHA returns the short HEAD commit of the ai-workflows repo.
// harness files live at tests/e2e/implement/harness/ — 4× ".." reaches repo root.
func workflowGitSHA() string {
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		return ""
	}
	repoRoot := filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", "..", ".."))
	out, err := exec.Command("git", "-C", repoRoot, "rev-parse", "--short", "HEAD").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}
