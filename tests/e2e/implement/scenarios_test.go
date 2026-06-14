package implement_test

import (
	. "github.com/onsi/ginkgo/v2"

	"github.com/ai-workflows/tests/e2e/implement/harness"
)

// TableArgs builds the variadic args slice for DescribeTable in Ginkgo v2 (v2.13+),
// where the signature is DescribeTable(description string, args ...any).
// Pass the spec function first, then all scenario entries.
func TableArgs(f any, entries []TableEntry) []any {
	args := make([]any, 0, 1+len(entries))
	args = append(args, f)
	for _, e := range entries {
		args = append(args, e)
	}
	return args
}

// allScenarios is the canonical list of Scenario values.
// suite_test.go reads this directly for cache warming (bypassing TableEntry
// whose parameters field is unexported in Ginkgo v2.13+).
//
// To add a new test case:
//  1. Append a Scenario value here.
//  2. Create fixtures/{ID}/ with stories/, docs-repo/, and artifacts/.
var allScenarios = []harness.Scenario{
	{
		ID:       "EDM-3895",
		StoryKey: "EDM-3895",
		Repo: harness.RepoConfig{
			URL:            "https://github.com/flightctl/flightctl",
			PreFixSHA:      "8abf88fa2",
			PostFixSHA:     "adcf70ee5",
			FeatureBranch:  "EDM-3895-restore-archive-argument",
			PlanBaseBranch: "EDM-3885",
			DocsRepo: harness.DocsRepoConfig{
				URL:    "https://github.com/flightctl/design-docs",
				SHA:    "49590e40b1532ad49c8313369c13fab549927957",
				Branch: "main",
			},
		},
		Build: harness.BuildConfig{
			Compile: "make build",
			// Scope to the packages touched by this story. Running the full
			// "make unit-test" would fail on pre-existing failures in unrelated
			// packages (internal/service, internal/tpm, etc.) that exist at the
			// PreFixSHA and are not caused by the agent's changes.
			Test: "go test ./internal/restore/... ./cmd/flightctl-restore/...",
			// AssertCoverage derives packages from NewFiles and filters output
			// to only the new implementation files, so pre-existing uncovered
			// code in the same package doesn't affect the result.
			CoverageThreshold: 70,
		},
		TokenBudgets: harness.TokenBudgets{
			Ingest:   150_000,
			Plan:     50_000,
			Code:     200_000,
			Validate: 80_000,
			Publish:  40_000,
		},
		Assertions: harness.Assertions{
			Ingest: harness.IngestAssertions{
				RequiredSections:          []string{"Story Summary", "Validation Profile"},
				ValidationProfileContains: []string{"make unit-test", "make lint"},
			},
			Plan: harness.PlanAssertions{
				RequiredSections: []string{"Branch", "Task Breakdown", "Test Strategy", "Acceptance Criteria Coverage"},
				MustMention:      []string{"internal/restore/archive.go", "archive_test.go"},
				MinTasks:         3,
			},
			Code: harness.CodeAssertions{
				NewFiles:         []string{"internal/restore/archive.go", "internal/restore/archive_test.go"},
				MinTestFunctions: 3,
			},
			Validate: harness.ValidateAssertions{
				ExpectedVerdict: "PASS",
			},
			Publish: harness.PublishAssertions{
				TitleContains: "EDM-3895",
				BaseBranch:    "main",
			},
		},
	},
}

// Scenarios returns allScenarios wrapped as Ginkgo TableEntry values.
func Scenarios() []TableEntry {
	entries := make([]TableEntry, 0, len(allScenarios))
	for _, s := range allScenarios {
		entries = append(entries, Entry(s.ID, s))
	}
	return entries
}
