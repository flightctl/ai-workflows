package harness

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// makeTestRepo creates a git repo at dir with one commit containing a single
// file. Returns the full commit SHA.
func makeTestRepo(t *testing.T, dir string) string {
	t.Helper()
	must := func(args ...string) {
		t.Helper()
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("%v: %v\n%s", args, err, out)
		}
	}
	must("git", "init", "-b", "main")
	must("git", "config", "user.email", "test@test")
	must("git", "config", "user.name", "Test")
	if err := os.WriteFile(filepath.Join(dir, "README.md"), []byte("hello\n"), 0o644); err != nil {
		t.Fatalf("write README: %v", err)
	}
	must("git", "add", ".")
	must("git", "commit", "-m", "initial")

	out, err := exec.Command("git", "-C", dir, "rev-parse", "HEAD").Output()
	if err != nil {
		t.Fatalf("rev-parse HEAD: %v", err)
	}
	return strings.TrimSpace(string(out))
}

// TestGithubAuthURL verifies URL rewriting when GITHUB_TOKEN is set.
func TestGithubAuthURL(t *testing.T) {
	t.Setenv("GITHUB_TOKEN", "")
	t.Setenv("GH_TOKEN", "")

	plain := "https://github.com/owner/repo"

	// No token → unchanged
	if got := githubAuthURL(plain); got != plain {
		t.Errorf("no token: want %s, got %s", plain, got)
	}

	// GITHUB_TOKEN set
	t.Setenv("GITHUB_TOKEN", "ghp_secret")
	got := githubAuthURL(plain)
	if !strings.Contains(got, "x-access-token:ghp_secret@github.com") {
		t.Errorf("GITHUB_TOKEN: unexpected URL %s", got)
	}
	if strings.Contains(got, "ghp_secret@github.com/owner/repo") == false {
		t.Errorf("GITHUB_TOKEN: path not preserved: %s", got)
	}
	t.Setenv("GITHUB_TOKEN", "")

	// GH_TOKEN set
	t.Setenv("GH_TOKEN", "gho_tok")
	got = githubAuthURL(plain)
	if !strings.Contains(got, "x-access-token:gho_tok@github.com") {
		t.Errorf("GH_TOKEN: unexpected URL %s", got)
	}
	t.Setenv("GH_TOKEN", "")

	// Non-GitHub URL → unchanged
	other := "https://gitlab.com/owner/repo"
	t.Setenv("GITHUB_TOKEN", "tok")
	if got := githubAuthURL(other); got != other {
		t.Errorf("non-github: want unchanged, got %s", got)
	}
}

// TestIsWarmedSHA verifies the clone-completeness check.
func TestIsWarmedSHA(t *testing.T) {
	dir := t.TempDir()
	sha := makeTestRepo(t, dir)

	// Full SHA and abbreviated prefix should both match.
	if !isWarmedSHA(dir, sha) {
		t.Errorf("full SHA: expected true for warmed repo")
	}
	if !isWarmedSHA(dir, sha[:9]) {
		t.Errorf("prefix SHA: expected true for warmed repo")
	}

	// Wrong SHA → false
	if isWarmedSHA(dir, "0000000000000000000000000000000000000000") {
		t.Error("wrong SHA: expected false")
	}

	// Non-existent dir → false
	if isWarmedSHA(filepath.Join(dir, "nonexistent"), sha) {
		t.Error("missing dir: expected false")
	}
}

// TestSetupCodeRemote verifies that a bare local code remote is created with
// the expected branch, HEAD is correct, and the working-copy origin is
// redirected to file://.
func TestSetupCodeRemote(t *testing.T) {
	// Source repo (simulates the cached clone).
	srcDir := t.TempDir()
	sha := makeTestRepo(t, srcDir)

	remotePath := filepath.Join(t.TempDir(), "code-remote.git")
	destDir := t.TempDir()
	// Set up a git repo at dest that has "origin" pointing somewhere.
	must := func(args ...string) {
		t.Helper()
		cmd := exec.Command(args[0], args[1:]...)
		if out, err := cmd.CombinedOutput(); err != nil {
			t.Fatalf("%v: %v\n%s", args, err, out)
		}
	}
	// Clone srcDir to destDir so it has an origin remote.
	must("git", "clone", srcDir, destDir)
	// Poison push URL (matches what warmSHA does).
	must("git", "-C", destDir, "remote", "set-url", "--push", "origin", "DISABLED")
	must("git", "-C", destDir, "config", "user.email", "test@test")
	must("git", "-C", destDir, "config", "user.name", "Test")

	r := RepoConfig{
		URL:            "https://github.com/test/repo",
		PreFixSHA:      sha,
		PlanBaseBranch: "release-1",
	}

	setupCodeRemote(t, r, srcDir, remotePath, destDir)

	// Bare remote must exist.
	if _, err := os.Stat(filepath.Join(remotePath, "HEAD")); err != nil {
		t.Fatalf("bare remote HEAD missing: %v", err)
	}

	// HEAD in bare remote must point to the right branch.
	headBytes, _ := os.ReadFile(filepath.Join(remotePath, "HEAD"))
	if !strings.Contains(string(headBytes), "release-1") {
		t.Errorf("bare remote HEAD: want release-1, got %s", string(headBytes))
	}

	// Branch in bare remote must resolve to the correct commit.
	branchSHA, err := exec.Command("git", "-C", remotePath, "rev-parse", "release-1").Output()
	if err != nil {
		t.Fatalf("rev-parse branch in bare: %v", err)
	}
	if !strings.HasPrefix(strings.TrimSpace(string(branchSHA)), sha[:9]) {
		t.Errorf("branch SHA mismatch: want %s, got %s", sha[:9], strings.TrimSpace(string(branchSHA)))
	}

	// Working copy origin fetch URL must be file:// path to bare remote.
	originURL, err := exec.Command("git", "-C", destDir, "remote", "get-url", "origin").Output()
	if err != nil {
		t.Fatalf("get-url origin: %v", err)
	}
	if got := strings.TrimSpace(string(originURL)); !strings.HasPrefix(got, "file://") {
		t.Errorf("origin fetch URL: want file://, got %s", got)
	}
	if !strings.Contains(string(originURL), remotePath) {
		t.Errorf("origin fetch URL: want path %s, got %s", remotePath, string(originURL))
	}

	// Push URL must remain DISABLED.
	pushURL, err := exec.Command("git", "-C", destDir, "remote", "get-url", "--push", "origin").Output()
	if err != nil {
		t.Fatalf("get-url --push origin: %v", err)
	}
	if !strings.Contains(string(pushURL), "DISABLED") {
		t.Errorf("push URL should be DISABLED, got %s", string(pushURL))
	}
}

// TestSetupCodeRemote_DefaultBranch verifies PlanBaseBranch defaults to "main".
func TestSetupCodeRemote_DefaultBranch(t *testing.T) {
	srcDir := t.TempDir()
	makeTestRepo(t, srcDir)

	remotePath := filepath.Join(t.TempDir(), "code-remote.git")
	destDir := t.TempDir()
	exec.Command("git", "clone", srcDir, destDir).Run()                                           //nolint:errcheck
	exec.Command("git", "-C", destDir, "remote", "set-url", "--push", "origin", "DISABLED").Run() //nolint:errcheck

	r := RepoConfig{URL: "https://github.com/test/repo"}
	setupCodeRemote(t, r, srcDir, remotePath, destDir)

	headBytes, _ := os.ReadFile(filepath.Join(remotePath, "HEAD"))
	if !strings.Contains(string(headBytes), "main") {
		t.Errorf("default branch: want main, got %s", string(headBytes))
	}
}

// TestSetupDocsRemote verifies a docs working copy + bare remote are created
// and the origin remote is wired correctly.
func TestSetupDocsRemote(t *testing.T) {
	// Source repo (simulates the cached docs clone).
	srcDir := t.TempDir()
	sha := makeTestRepo(t, srcDir)

	checkoutPath := filepath.Join(t.TempDir(), "docs")
	remotePath := filepath.Join(t.TempDir(), "docs-remote.git")

	d := DocsRepoConfig{
		URL:    "https://github.com/test/design-docs",
		SHA:    sha,
		Branch: "main",
	}

	// Temporarily override cacheRoot to return srcDir's parent so cacheKey
	// lookup finds srcDir. We do this by setting the env var that cacheRoot
	// reads and creating the expected directory name.
	cacheDir := t.TempDir()
	t.Setenv("E2E_REPO_CACHE", cacheDir)
	key := cacheKey(d.URL, d.SHA)
	cachedPath := filepath.Join(cacheDir, key)
	if err := exec.Command("cp", "-a", srcDir+"/.", cachedPath).Run(); err != nil {
		t.Fatalf("seed cache: %v", err)
	}

	ok := setupDocsRemote(t, d, checkoutPath, remotePath)
	if !ok {
		t.Fatal("setupDocsRemote: expected ok=true")
	}

	// Working copy must exist and have a file from the repo.
	if _, err := os.Stat(filepath.Join(checkoutPath, "README.md")); err != nil {
		t.Errorf("README.md missing in docs checkout: %v", err)
	}

	// Bare remote HEAD must point to main.
	headBytes, _ := os.ReadFile(filepath.Join(remotePath, "HEAD"))
	if !strings.Contains(string(headBytes), "main") {
		t.Errorf("docs bare remote HEAD: want main, got %s", string(headBytes))
	}

	// Checkout origin fetch URL must be file://.
	originURL, _ := exec.Command("git", "-C", checkoutPath, "remote", "get-url", "origin").Output()
	if !strings.HasPrefix(strings.TrimSpace(string(originURL)), "file://") {
		t.Errorf("docs origin URL: want file://, got %s", string(originURL))
	}

	// Push URL must be DISABLED.
	pushURL, _ := exec.Command("git", "-C", checkoutPath, "remote", "get-url", "--push", "origin").Output()
	if !strings.Contains(string(pushURL), "DISABLED") {
		t.Errorf("docs push URL: want DISABLED, got %s", string(pushURL))
	}
}

// TestSetupDocsRemote_Empty verifies the no-op path when DocsRepo is not configured.
func TestSetupDocsRemote_Empty(t *testing.T) {
	ok := setupDocsRemote(t, DocsRepoConfig{}, t.TempDir(), t.TempDir())
	if ok {
		t.Error("empty DocsRepoConfig: expected ok=false")
	}
}
