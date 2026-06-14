package implement_test

import (
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"

	"github.com/ai-workflows/tests/e2e/implement/harness"
)

// full_workflow_test.go runs every phase in sequence within a single shared
// project directory, verifying that artifacts produced by each phase are
// consumed correctly by the next.
var _ = Describe("full workflow", func() {
	DescribeTable("runs all phases end-to-end",
		TableArgs(func(s harness.Scenario) {
			By("preparing repo at pre-fix SHA")
			repo := harness.PrepareRepo(GinkgoT(), s, s.Repo.PreFixSHA)

			// Start the fixture container before any phase so that claude runs
			// with the full project toolchain available throughout all phases.
			By("starting fixture container")
			fc := harness.StartFixtureContainer(GinkgoT(), s, repo)

			report := harness.NewRunReport(s)

			// ── Phase 1: ingest ───────────────────────────────────────────────
			By("starting mock Jira MCP")
			mcp := harness.StartMockMCP(GinkgoT(), s)

			By("running /implement:ingest " + s.StoryKey)
			r := harness.RunPhase(GinkgoT(), "ingest", repo, s, fc,
				map[string]string{"JIRA_MCP_URL": mcp.URL}, GinkgoWriter)
			Expect(r.ExitCode).To(Equal(0), "ingest exited %d\n%s", r.ExitCode, r.Stderr)
			report.RecordPhase("ingest", r)

			By("asserting 01-context.md")
			harness.AssertIngest(GinkgoT(), repo, s)

			// ── Phase 2: plan ─────────────────────────────────────────────────
			By("running /implement:plan " + s.StoryKey)
			r = harness.RunPhase(GinkgoT(), "plan", repo, s, fc, nil, GinkgoWriter)
			Expect(r.ExitCode).To(Equal(0), "plan exited %d\n%s", r.ExitCode, r.Stderr)
			report.RecordPhase("plan", r)

			By("asserting 02-plan.md")
			harness.AssertPlan(GinkgoT(), repo, s)

			// ── Phase 3: code ─────────────────────────────────────────────────
			By("running /implement:code " + s.StoryKey)
			r = harness.RunPhase(GinkgoT(), "code", repo, s, fc, nil, GinkgoWriter)
			Expect(r.ExitCode).To(Equal(0), "code exited %d\n%s", r.ExitCode, r.Stderr)
			report.RecordPhase("code", r)

			By("asserting files and commits")
			harness.AssertCode(GinkgoT(), repo, s)

			By("compile check")
			harness.AssertBuildPasses(GinkgoT(), fc, s)

			By("agent's own tests pass")
			harness.AssertTestsPassed(GinkgoT(), fc, s)

			By("coverage check")
			harness.AssertCoverage(GinkgoT(), fc, repo, s)

			// ── Phase 4: validate ─────────────────────────────────────────────
			By("running /implement:validate " + s.StoryKey)
			r = harness.RunPhase(GinkgoT(), "validate", repo, s, fc, nil, GinkgoWriter)
			Expect(r.ExitCode).To(Equal(0), "validate exited %d\n%s", r.ExitCode, r.Stderr)
			report.RecordPhase("validate", r)

			By("asserting validation report")
			harness.AssertValidate(GinkgoT(), repo, s)

			By("generating comparison report (informational)")
			cmp := harness.CompareImplementations(GinkgoT(), repo, s, report)
			report.RecordQuality(cmp)

			// ── Phase 5: publish ──────────────────────────────────────────────
			By("initialising local bare repo as push remote")
			harness.InitBareRemote(GinkgoT(), repo)

			By("running /implement:publish " + s.StoryKey)
			r = harness.RunPhase(GinkgoT(), "publish", repo, s, fc, nil, GinkgoWriter)
			Expect(r.ExitCode).To(Equal(0), "publish exited %d\n%s", r.ExitCode, r.Stderr)
			report.RecordPhase("publish", r)

			By("asserting PR record captured by mock gh")
			harness.AssertPublish(GinkgoT(), repo, s)

			By("writing run report")
			report.Write(GinkgoT(), repo)
		}, Scenarios())...,
	)
})
