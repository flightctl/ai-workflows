package implement_test

import (
	"os/exec"
	"testing"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"

	"github.com/ai-workflows/tests/e2e/implement/harness"
)

func TestImplementSkill(t *testing.T) {
	RegisterFailHandler(Fail)
	RunSpecs(t, "Implement Skill E2E Suite")
}

var _ = SynchronizedBeforeSuite(func() []byte {
	// Runs once on node 1 (or the only node in non-parallel mode).

	// Claude CLI now runs inside the fixture container (not in the e2e container),
	// so there is no local binary to check here. Authentication errors will surface
	// on the first RunPhase call with a clear error message from claude itself.
	GinkgoWriter.Println("NOTE: claude CLI runs inside the fixture container.")
	GinkgoWriter.Println("      Auth errors (API key, Vertex AI creds) will surface on the first phase.")

	// 1. Build the mock gh binary that the publish phase will invoke.
	By("building mock gh binary")
	cmd := exec.Command("go", "build", "-o", "fixtures/bin/gh", "./mock_gh/")
	out, buildErr := cmd.CombinedOutput()
	Expect(buildErr).NotTo(HaveOccurred(), "build mock gh:\n%s", out)

	// 2. Warm the repo cache for every scenario so actual test specs
	//    just copy from the local cache instead of cloning each time.
	By("warming repo cache for all scenarios")
	for _, s := range allScenarios {
		harness.WarmCache(s)
	}

	return nil
}, func([]byte) {
	// runs on every parallel node after node-1 setup completes — nothing to do.
})
