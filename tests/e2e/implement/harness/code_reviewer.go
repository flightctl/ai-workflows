package harness

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// ComparisonReport is written to .artifacts/e2e-reports/{id}-comparison.json.
// It is informational only — it never fails a test.
//
// In addition to quality scores it embeds the per-phase token usage from the
// RunReport so the file is self-contained for historical analysis.
type ComparisonReport struct {
	ScenarioID    string                 `json:"scenario_id"`
	Verdict       string                 `json:"verdict"` // "BETTER", "EQUIVALENT", "WORSE"
	Summary       string                 `json:"summary"`
	Correctness   int                    `json:"correctness"` // 0-10
	Readability   int                    `json:"readability"`
	TestCoverage  int                    `json:"test_coverage"`
	ErrorHandling int                    `json:"error_handling"`
	Notes         string                 `json:"notes"`
	Phases        map[string]PhaseRecord `json:"phases,omitempty"`
}

// CompareImplementations asks claude to compare the agent's implementation
// against the reference (PostFixSHA) implementation using a structured rubric.
// The report is written to .artifacts/e2e-reports/{id}-comparison.json relative
// to the project directory. Returns the report for embedding in a RunReport;
// returns nil on any failure (failures are logged as warnings, never fatal).
//
// report is used to embed per-phase token usage in the written JSON file so it
// is self-contained. Pass nil to omit token data (e.g. when called from a
// phase-only test that did not run all phases).
func CompareImplementations(t T, projectDir string, s Scenario, report *RunReport) *ComparisonReport {
	t.Helper()

	refDir := filepath.Join(cacheRoot(), cacheKey(s.Repo.URL, s.Repo.PostFixSHA))

	// Build context: compare each new file the agent should have produced
	// against the same file in the reference (PostFixSHA) checkout.
	var agentFiles, refFiles string
	for _, rel := range s.Assertions.Code.NewFiles {
		agentContent, _ := os.ReadFile(filepath.Join(projectDir, rel))
		refContent, _ := os.ReadFile(filepath.Join(refDir, rel))

		agentFiles += fmt.Sprintf("\n\n### Agent: %s\n```go\n%s\n```", rel, agentContent)
		refFiles += fmt.Sprintf("\n\n### Reference: %s\n```go\n%s\n```", rel, refContent)
	}

	prompt := fmt.Sprintf(`Compare these two Go implementations of the same feature (%s).

Score each dimension from 0–10 and give a verdict of BETTER, EQUIVALENT, or WORSE
(agent vs reference). Return ONLY a JSON object matching this schema exactly:

{
  "verdict": "BETTER|EQUIVALENT|WORSE",
  "summary": "one sentence",
  "correctness": 0,
  "readability": 0,
  "test_coverage": 0,
  "error_handling": 0,
  "notes": "optional details"
}

## Agent Implementation
%s

## Reference Implementation
%s`, s.StoryKey, agentFiles, refFiles)

	cmd := exec.Command(claudeBin(), "--print", "--verbose", "--output-format", "stream-json", "--max-turns", "1", prompt)
	cmd.Dir = projectDir
	cmd.Env = safeEnv(nil)

	out, err := cmd.Output()
	if err != nil {
		t.Logf("WARNING: code comparison failed: %v", err)
		return nil
	}

	// Extract JSON from the claude response envelope.
	var resultText string
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var ev streamEvent
		if jsonErr := json.Unmarshal([]byte(line), &ev); jsonErr == nil && ev.Type == "result" {
			resultText = ev.Result
			break
		}
	}
	if resultText == "" {
		t.Logf("WARNING: no result event in claude output:\n%.500s", string(out))
		return nil
	}

	var comparison ComparisonReport
	if jsonErr := json.Unmarshal([]byte(resultText), &comparison); jsonErr != nil {
		t.Logf("WARNING: parse comparison report: %v\nraw: %s", jsonErr, resultText)
		return nil
	}
	comparison.ScenarioID = s.ID

	// Embed per-phase token usage if a RunReport was provided.
	if report != nil && len(report.Phases) > 0 {
		comparison.Phases = report.Phases
	}

	outDir := filepath.Join(projectDir, ".artifacts", "e2e-reports")
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		t.Logf("WARNING: mkdir e2e-reports: %v", err)
		return nil
	}
	data, _ := json.MarshalIndent(comparison, "", "  ")
	reportPath := filepath.Join(outDir, s.ID+"-comparison.json")
	if err := os.WriteFile(reportPath, data, 0o644); err != nil {
		t.Logf("WARNING: write comparison report: %v", err)
		return nil
	}

	t.Logf("Comparison report (%s): verdict=%s correctness=%d readability=%d test_coverage=%d",
		s.ID, comparison.Verdict, comparison.Correctness, comparison.Readability, comparison.TestCoverage)
	return &comparison
}
