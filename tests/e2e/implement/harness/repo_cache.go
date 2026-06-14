package harness

import (
	"crypto/sha256"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// cacheRoot returns the directory used to store blobless clones keyed by repo+sha.
func cacheRoot() string {
	if v := os.Getenv("E2E_REPO_CACHE"); v != "" {
		return v
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".cache", "e2e-repos")
}

// cacheKey returns a filesystem-safe key for a repo+sha pair.
func cacheKey(repoURL, sha string) string {
	h := sha256.Sum256([]byte(repoURL + "#" + sha))
	return fmt.Sprintf("%x", h[:8])
}

// skillsRoot returns the absolute path to the implement skill directory in this repo.
// When AI_WORKFLOWS_ROOT is set (e.g. inside the e2e container where the repo is
// mounted read-only at /workspace) it is used directly, avoiding the runtime.Caller
// path traversal that would break when tests are compiled from a temp copy.
func skillsRoot() string {
	if root := os.Getenv("AI_WORKFLOWS_ROOT"); root != "" {
		return filepath.Join(root, "implement")
	}
	_, file, _, _ := runtime.Caller(0)
	// file = tests/e2e/implement/harness/repo_cache.go
	// 4× ".." reaches the repo root (ai-workflows/)
	repoRoot := filepath.Join(filepath.Dir(file), "..", "..", "..", "..")
	return filepath.Clean(filepath.Join(repoRoot, "implement"))
}

// fixturesRoot returns the absolute path to tests/e2e/implement/fixtures/.
func fixturesRoot() string {
	_, file, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(file), "..", "fixtures")
}

// WarmCache ensures blobless clones of the code repo (both SHAs) and the docs
// repo (if configured) exist in the cache. Safe to call multiple times.
func WarmCache(s Scenario) {
	for _, sha := range []string{s.Repo.PreFixSHA, s.Repo.PostFixSHA} {
		warmSHA(s.Repo.URL, sha)
	}
	if s.Repo.DocsRepo.URL != "" && s.Repo.DocsRepo.SHA != "" {
		warmSHA(s.Repo.DocsRepo.URL, s.Repo.DocsRepo.SHA)
	}
}

// isWarmedSHA returns true when dest contains a fully-warmed clone at sha:
// the .git directory must exist AND git rev-parse HEAD must resolve to sha.
// This catches the case where a previous run completed the clone but failed
// during checkout, leaving .git without a checked-out working tree.
func isWarmedSHA(dest, sha string) bool {
	out, err := exec.Command("git", "-C", dest, "rev-parse", "HEAD").Output()
	if err != nil {
		return false
	}
	return strings.HasPrefix(strings.TrimSpace(string(out)), sha)
}

func warmSHA(repoURL, sha string) {
	dest := filepath.Join(cacheRoot(), cacheKey(repoURL, sha))
	// Verify both the clone and the checkout completed: rev-parse HEAD must
	// match the target SHA. A partial clone (clone done, checkout not) or a
	// stale leftover directory both cause this check to fail, triggering a
	// fresh clone.
	if isWarmedSHA(dest, sha) {
		return
	}
	// Remove any stale/partial directory left by a previous failed attempt.
	// git clone refuses to clone into a non-empty directory.
	if _, err := os.Stat(dest); err == nil {
		if rmErr := os.RemoveAll(dest); rmErr != nil {
			panic(fmt.Sprintf("remove stale cache dir %s: %v", dest, rmErr))
		}
	}
	if err := os.MkdirAll(dest, 0o755); err != nil {
		panic(fmt.Sprintf("create cache dir: %v", err))
	}
	run := func(args ...string) {
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Stdout = os.Stderr
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			panic(fmt.Sprintf("cmd %v: %v", args, err))
		}
	}
	// Use an authenticated URL for cloning when a token is available (required
	// for private repos; also avoids anonymous rate limits in CI).
	// The token must stay in the remote URL through checkout: blobless clones
	// fetch blobs lazily during `git checkout`, so stripping the token before
	// checkout causes a second authentication failure.
	// Only after checkout completes do we reset the stored remote to the plain
	// URL so the token is never persisted on disk.
	cloneURL := githubAuthURL(repoURL)
	run("git", "clone", "--filter=blob:none", "--no-checkout", cloneURL, dest)
	run("git", "-C", dest, "checkout", sha)
	// Strip the token and poison push URL so no test can accidentally push to
	// the real remote or expose credentials stored on disk.
	run("git", "-C", dest, "remote", "set-url", "origin", repoURL)
	run("git", "-C", dest, "remote", "set-url", "--push", "origin", "DISABLED")
	// Allow this clone to be used as a fetch source (via file:// URL) for bare
	// remotes created by setupCodeRemote / setupDocsRemote. Without this flag,
	// git-upload-pack does not advertise the "filter" capability, causing the
	// client's --filter=blob:none to be silently ignored — after which the
	// server tries to enumerate all objects including promised blobs and fails.
	run("git", "-C", dest, "config", "uploadpack.allowFilter", "true")
}

// githubAuthURL injects a GitHub token into a https://github.com/ URL when
// GITHUB_TOKEN or GH_TOKEN is set in the environment. The token is used only
// for the clone operation; callers must reset the stored remote URL to the
// plain URL afterward so the token is never written to disk.
func githubAuthURL(rawURL string) string {
	for _, key := range []string{"GITHUB_TOKEN", "GH_TOKEN"} {
		if tok := os.Getenv(key); tok != "" {
			const prefix = "https://github.com/"
			if len(rawURL) >= len(prefix) && rawURL[:len(prefix)] == prefix {
				return "https://x-access-token:" + tok + "@github.com/" + rawURL[len(prefix):]
			}
			return rawURL
		}
	}
	return rawURL
}

// PrepareRepo copies the cached clone to a fresh temp directory,
// injects the implement skill, and seeds the prd config.
// The returned path is the project root to pass to RunPhase.
//
// Directory layout created inside the test's temp dir:
//
//	<outer>/
//	  project/      ← copy of the cloned repo (this path is returned)
//	  skills/       ← symlink → <skillsRoot>/skills/
//
// The `skills/` symlink at the sibling level ensures that when the claude CLI
// executes a command with CWD=<outer>/project/, the path `../skills/controller.md`
// referenced in command templates resolves to <outer>/skills/controller.md →
// <skillsRoot>/skills/controller.md as intended.
func PrepareRepo(t T, s Scenario, sha string) string {
	t.Helper()
	src := filepath.Join(cacheRoot(), cacheKey(s.Repo.URL, sha))

	// Use an outer wrapper so that ../skills/ is resolvable from the project root.
	outer := t.TempDir()
	dest := filepath.Join(outer, "project")
	if err := os.MkdirAll(dest, 0o755); err != nil {
		t.Fatalf("mkdir project: %v", err)
	}

	// Copy the clone (cp -a preserves git metadata).
	cmd := exec.Command("cp", "-a", src+"/.", dest)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		t.Fatalf("copy repo: %v", err)
	}

	// Sibling skills/ symlink: ../skills/controller.md from project CWD resolves here.
	if err := os.Symlink(filepath.Join(skillsRoot(), "skills"), filepath.Join(outer, "skills")); err != nil && !os.IsExist(err) {
		t.Fatalf("symlink ../skills: %v", err)
	}

	// Inject implement skill for the claude CLI.
	//
	// The claude CLI discovers slash commands at .claude/commands/{wf}/.
	claudeCmdsDir := filepath.Join(dest, ".claude", "commands")
	if err := os.MkdirAll(claudeCmdsDir, 0o755); err != nil {
		t.Fatalf("mkdir .claude/commands: %v", err)
	}
	cmdSymlink := filepath.Join(claudeCmdsDir, "implement")
	if err := os.Symlink(filepath.Join(skillsRoot(), "commands"), cmdSymlink); err != nil && !os.IsExist(err) {
		t.Fatalf("symlink .claude/commands/implement: %v", err)
	}

	// Configure a git identity so the code phase can commit without prompting.
	// These are test-only values; the skill uses the project's commit format.
	for _, kv := range [][]string{
		{"user.email", "e2e-test@ai-workflows"},
		{"user.name", "AI Workflows E2E"},
	} {
		gc := exec.Command("git", "-C", dest, "config", kv[0], kv[1])
		if out, err := gc.CombinedOutput(); err != nil {
			t.Fatalf("git config %s: %v\n%s", kv[0], err, out)
		}
	}

	// Local code remote — PreFixSHA exposed as PlanBaseBranch (or main).
	// Redirects origin fetch URL to file:// so the skill never contacts GitHub.
	codeRemote := filepath.Join(outer, "code-remote.git")
	setupCodeRemote(t, s.Repo, src, codeRemote, dest)

	// Local docs remote — working copy + bare remote inside outer/ so they
	// are accessible from the fixture container at the same absolute path.
	docsCheckout := filepath.Join(outer, "docs")
	docsRemote := filepath.Join(outer, "docs-remote.git")
	docsOK := setupDocsRemote(t, s.Repo.DocsRepo, docsCheckout, docsRemote)

	// Seed .artifacts/prd/config.json. When the docs repo is configured,
	// point at the local paths; fall back to the static fixture snapshot.
	var docsRepoPath, docsRepoRemote string
	if docsOK {
		docsRepoPath = docsCheckout
		docsRepoRemote = "file://" + docsRemote
	} else {
		docsRepoPath = filepath.Join(fixturesRoot(), s.ID, "docs-repo")
		docsRepoRemote = "https://example.com/docs"
	}
	artifactsDir := filepath.Join(dest, ".artifacts", "prd")
	if err := os.MkdirAll(artifactsDir, 0o755); err != nil {
		t.Fatalf("mkdir artifacts: %v", err)
	}
	config := fmt.Sprintf(`{"docs_repo_path": %q, "docs_repo_remote": %q}`, docsRepoPath, docsRepoRemote)
	if err := os.WriteFile(filepath.Join(artifactsDir, "config.json"), []byte(config), 0o644); err != nil {
		t.Fatalf("write prd config: %v", err)
	}

	return dest
}

// SeedArtifacts copies pre-seeded artifact files from fixtures/EDM-XXXX/artifacts/
// into the project's .artifacts/implement/EDM-XXXX/ directory.
func SeedArtifacts(t T, projectDir string, s Scenario, files ...string) {
	t.Helper()
	src := filepath.Join(fixturesRoot(), s.ID, "artifacts")
	dest := filepath.Join(projectDir, ".artifacts", "implement", s.StoryKey)
	if err := os.MkdirAll(dest, 0o755); err != nil {
		t.Fatalf("mkdir artifact dest: %v", err)
	}
	for _, f := range files {
		data, err := os.ReadFile(filepath.Join(src, f))
		if err != nil {
			t.Fatalf("read seed artifact %s: %v", f, err)
		}
		if err := os.WriteFile(filepath.Join(dest, f), data, 0o644); err != nil {
			t.Fatalf("write seed artifact %s: %v", f, err)
		}
	}
}

// CheckoutBranch creates a new local branch at the current HEAD and checks it
// out. Used by publish tests to ensure the repo is on a named branch (not a
// detached HEAD) before running the publish skill.
func CheckoutBranch(t T, projectDir, branch string) {
	t.Helper()
	cmd := exec.Command("git", "checkout", "-b", branch)
	cmd.Dir = projectDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git checkout -b %s: %v\n%s", branch, err, out)
	}
}

// setupCodeRemote creates a bare git repo at remotePath that exposes only
// PreFixSHA as PlanBaseBranch (or "main"), then redirects the project's
// origin fetch URL to it via file://. The push URL (DISABLED, inherited from
// the cached clone via cp -a) is left unchanged so no test can push to GitHub.
//
// Using a single isolated branch prevents the skill from seeing commits beyond
// PreFixSHA — the post-fix implementation is invisible to the AI.
func setupCodeRemote(t T, r RepoConfig, cachedSrc, remotePath, dest string) {
	t.Helper()
	branch := r.PlanBaseBranch
	if branch == "" {
		branch = "main"
	}
	runIn := func(dir string, args ...string) {
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		cmd.Stdout = os.Stderr
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			t.Fatalf("setupCodeRemote %v: %v", args, err)
		}
	}
	// Allow the cached clone to advertise the "filter" capability when used as
	// a fetch source via file:// URL. Without this, git-upload-pack does not
	// include "filter" in its capability advertisement even on modern git,
	// causing the client's --filter=blob:none to be silently ignored and the
	// server to enumerate all objects — including promised blobs it cannot
	// deliver (GIT_NO_LAZY_FETCH=1 is set automatically in upload-pack).
	// This is an idempotent no-op on clones that already have the config.
	if out, err := exec.Command("git", "-C", cachedSrc, "config", "uploadpack.allowFilter", "true").CombinedOutput(); err != nil {
		t.Fatalf("setupCodeRemote git config uploadpack.allowFilter: %v\n%s", err, out)
	}
	runIn("", "git", "init", "--bare", remotePath)
	// Fetch only HEAD (PreFixSHA) from the cached clone — single branch,
	// no future commits visible to the AI.
	// file:// forces git to spawn git-upload-pack (which honours --filter).
	// A bare path would use the local transport which bypasses upload-pack and
	// silently ignores --filter, falling back to enumerating all objects.
	runIn("", "git", "--git-dir", remotePath, "fetch", "--filter=blob:none", "file://"+cachedSrc, "HEAD:refs/heads/"+branch)
	if err := os.WriteFile(
		filepath.Join(remotePath, "HEAD"),
		[]byte("ref: refs/heads/"+branch+"\n"),
		0o644,
	); err != nil {
		t.Fatalf("setupCodeRemote write HEAD: %v", err)
	}
	// Redirect origin fetch; push URL (DISABLED) is preserved from cp -a.
	runIn(dest, "git", "remote", "set-url", "origin", "file://"+remotePath)
}

// setupDocsRemote creates a writable working copy of the docs repo at
// checkoutPath and a bare remote at remotePath, both from the cached clone
// keyed by d.URL+d.SHA. The working copy's origin is wired to the bare remote
// (file://) so the skill can fetch and push design docs without any network
// access.
//
// If DocsRepo is not configured (empty URL or SHA), this is a no-op and both
// paths are left uncreated.
func setupDocsRemote(t T, d DocsRepoConfig, checkoutPath, remotePath string) (ok bool) {
	t.Helper()
	if d.URL == "" || d.SHA == "" {
		return false
	}
	branch := d.Branch
	if branch == "" {
		branch = "main"
	}
	cachedSrc := filepath.Join(cacheRoot(), cacheKey(d.URL, d.SHA))
	runIn := func(dir string, args ...string) {
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		cmd.Stdout = os.Stderr
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil {
			t.Fatalf("setupDocsRemote %v: %v", args, err)
		}
	}
	if err := os.MkdirAll(checkoutPath, 0o755); err != nil {
		t.Fatalf("setupDocsRemote mkdir %s: %v", checkoutPath, err)
	}
	// Copy cached clone → outer/docs/ (writable working copy for the skill).
	runIn("", "cp", "-a", cachedSrc+"/.", checkoutPath)
	// Create a bare remote with a single branch at the fixture SHA.
	// Same uploadpack.allowFilter + file:// + --filter=blob:none rationale as setupCodeRemote.
	if out, err := exec.Command("git", "-C", checkoutPath, "config", "uploadpack.allowFilter", "true").CombinedOutput(); err != nil {
		t.Fatalf("setupDocsRemote git config uploadpack.allowFilter: %v\n%s", err, out)
	}
	runIn("", "git", "init", "--bare", remotePath)
	runIn("", "git", "--git-dir", remotePath, "fetch", "--filter=blob:none", "file://"+checkoutPath, "HEAD:refs/heads/"+branch)
	if err := os.WriteFile(
		filepath.Join(remotePath, "HEAD"),
		[]byte("ref: refs/heads/"+branch+"\n"),
		0o644,
	); err != nil {
		t.Fatalf("setupDocsRemote write HEAD: %v", err)
	}
	// Redirect origin in the working copy to the local bare remote.
	// The cached clone created by warmSHA always has an origin, but use "add"
	// as a fallback so setupDocsRemote is robust even for edge cases (e.g. a
	// manually seeded cache entry created with git init rather than git clone).
	if originOut, _ := exec.Command("git", "-C", checkoutPath, "remote", "get-url", "origin").Output(); len(originOut) > 0 {
		runIn(checkoutPath, "git", "remote", "set-url", "origin", "file://"+remotePath)
	} else {
		runIn(checkoutPath, "git", "remote", "add", "origin", "file://"+remotePath)
	}
	runIn(checkoutPath, "git", "remote", "set-url", "--push", "origin", "DISABLED")
	return true
}

// InitBareRemote creates a local bare git repo and sets it as the push remote,
// replacing the DISABLED sentinel. Used by publish tests.
func InitBareRemote(t T, projectDir string) string {
	t.Helper()
	bare := t.TempDir()
	cmd := exec.Command("git", "init", "--bare", bare)
	cmd.Dir = projectDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git init bare: %v\n%s", err, out)
	}
	cmd = exec.Command("git", "remote", "set-url", "--push", "origin", bare)
	cmd.Dir = projectDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("set push remote: %v\n%s", err, out)
	}
	return bare
}
