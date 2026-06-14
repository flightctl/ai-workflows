package harness

// Scenario describes one story + repo + revision combination.
// All scenario config lives here as typed Go fields — no YAML parsing at runtime.
type Scenario struct {
	ID           string
	StoryKey     string
	Repo         RepoConfig
	Build        BuildConfig
	TokenBudgets TokenBudgets
	Assertions   Assertions
}

// RepoConfig identifies the repository and the two key commits.
type RepoConfig struct {
	URL           string
	PreFixSHA     string // checkout for ingest/plan/code tests (feature not yet implemented)
	PostFixSHA    string // checkout for validate fixture (real implementation present)
	FeatureBranch string // branch name to create at PostFixSHA for publish tests
	// PlanBaseBranch is the branch the implementation plan's "## Branch / Base:"
	// section names. PrepareRepo creates a local bare remote that exposes this
	// branch at PreFixSHA so the code phase can do:
	//   git fetch origin && git checkout -b feature origin/PlanBaseBranch
	// without touching the real remote or exposing the post-fix implementation.
	// If empty, the local remote exposes "main" at PreFixSHA.
	PlanBaseBranch string
	// DocsRepo identifies the design-docs repository and the fixture revision.
	// PrepareRepo creates a local bare remote and working copy for this repo
	// inside outer/ so the skill never contacts the real docs remote.
	DocsRepo DocsRepoConfig
}

// DocsRepoConfig identifies the design-docs repository and the specific commit
// the fixture starts from. PrepareRepo creates an isolated local bare remote
// at outer/docs-remote.git and a working copy at outer/docs/ so that the
// implement skill can read and push design docs without network access.
type DocsRepoConfig struct {
	URL    string // e.g. "https://github.com/flightctl/flightctl-docs"
	SHA    string // commit exposed as HEAD of Branch in the local bare remote
	Branch string // branch name to expose (defaults to "main" if empty)
}

// BuildConfig holds the commands used to build and test the fixture project.
// All commands run inside a container built from fixtures/{ScenarioID}/Containerfile.
type BuildConfig struct {
	Compile           string
	Test              string
	CoverageThreshold int // minimum avg coverage % across new implementation files (0 = skip)
}

// TokenBudgets defines per-phase soft limits (warnings, not failures).
type TokenBudgets struct {
	Ingest   int
	Plan     int
	Code     int
	Validate int
	Publish  int
}

// Assertions groups per-phase assertion configs.
type Assertions struct {
	Ingest   IngestAssertions
	Plan     PlanAssertions
	Code     CodeAssertions
	Validate ValidateAssertions
	Publish  PublishAssertions
}

// IngestAssertions specifies what a correct 01-context.md must contain.
type IngestAssertions struct {
	RequiredSections          []string
	ValidationProfileContains []string
	BranchPattern             string
}

// PlanAssertions specifies what a correct 02-plan.md must contain.
type PlanAssertions struct {
	RequiredSections []string
	MustMention      []string
	MinTasks         int
}

// CodeAssertions specifies what a correct /code phase must produce.
type CodeAssertions struct {
	NewFiles         []string
	MinCommits       int
	MinTestFunctions int
}

// ValidateAssertions specifies what a correct 05-validation-report.md must contain.
type ValidateAssertions struct {
	ExpectedVerdict string // "PASS" or "FAIL"
}

// PublishAssertions specifies what a correct /publish phase must produce.
type PublishAssertions struct {
	TitleContains string
	BaseBranch    string
}
