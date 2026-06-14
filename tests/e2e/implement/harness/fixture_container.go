package harness

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
)

// claudeBinInFixture is the path to the claude CLI binary inside the fixture
// container (installed by the fixture Containerfile as the e2e user).
const claudeBinInFixture = "/home/e2e/.local/bin/claude"

// FixtureContainer holds a running podman container used for all claude CLI
// invocations and build/test commands within a single test scenario.
// Start it once per test with StartFixtureContainer; all operations run in it
// via RunClaude and Exec.
type FixtureContainer struct {
	id    string
	image string
	// mockGHDir is the path to the directory containing the mock gh binary
	// as seen from INSIDE the fixture container. It must be under outerDir
	// since that is the only user-data directory mounted into the container.
	mockGHDir string
}

// fixtureImageName returns a stable local image tag for the scenario.
func fixtureImageName(s Scenario) string {
	return "e2e-fixture-" + strings.ToLower(s.ID) + ":latest"
}

// fixtureImageCacheDir returns the host-persistent directory for fixture image tarballs.
// The e2e container mounts the host path here via E2E_IMAGES_CACHE.
func fixtureImageCacheDir() string {
	if v := os.Getenv("E2E_IMAGES_CACHE"); v != "" {
		return v
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".cache", "e2e-fixture-images")
}

// ensureFixtureImage returns the image tag for the scenario, building it if
// necessary. It uses a tarball cache keyed by the SHA-256 of the Containerfile
// content so that unchanged images survive container restarts without rebuilding.
//
// An advisory lock file (cacheTar+".lock") prevents two concurrent scenarios
// from racing on the same image build.
func ensureFixtureImage(t T, s Scenario) string {
	t.Helper()

	image := fixtureImageName(s)
	containerfileDir := filepath.Join(fixturesRoot(), s.ID)
	containerfile := filepath.Join(containerfileDir, "Containerfile")

	cfContent, err := os.ReadFile(containerfile)
	if err != nil {
		t.Fatalf("fixture Containerfile not found at %s: %v", containerfile, err)
	}
	// Also hash shared files (fixtures/<file>) so changes bust the cache.
	sharedFiles := []string{"mock-jira-mcp.py"}
	h := sha256.New()
	h.Write(cfContent)
	for _, sf := range sharedFiles {
		sfContent, sfErr := os.ReadFile(filepath.Join(filepath.Dir(containerfileDir), sf))
		if sfErr == nil {
			h.Write(sfContent)
		}
	}
	sum := h.Sum(nil)
	cacheKey := fmt.Sprintf("%x", sum[:8])

	cacheDir := fixtureImageCacheDir()
	cacheTar := filepath.Join(cacheDir, s.ID+"-"+cacheKey+".tar")

	// Fast path: image already in the local podman store (same container session).
	if exec.Command("podman", "image", "exists", image).Run() == nil {
		t.Logf("fixture image already in store: %s", image)
		return image
	}

	// Acquire an advisory lock so concurrent scenarios don't race on the same build.
	lockPath := cacheTar + ".lock"
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		t.Fatalf("create fixture cache dir: %v", err)
	}
	lockFile, lockErr := os.OpenFile(lockPath, os.O_CREATE|os.O_WRONLY, 0o644)
	if lockErr != nil {
		t.Fatalf("open lock file %s: %v", lockPath, lockErr)
	}
	defer lockFile.Close()
	if err := syscall.Flock(int(lockFile.Fd()), syscall.LOCK_EX); err != nil {
		t.Fatalf("acquire build lock %s: %v", lockPath, err)
	}
	defer syscall.Flock(int(lockFile.Fd()), syscall.LOCK_UN) //nolint:errcheck

	// Re-check after acquiring the lock — another goroutine may have built it.
	if exec.Command("podman", "image", "exists", image).Run() == nil {
		t.Logf("fixture image built by concurrent runner: %s", image)
		return image
	}

	// Medium path: load from the persistent tarball cache.
	if _, statErr := os.Stat(cacheTar); statErr == nil {
		t.Logf("loading fixture image from cache: %s", cacheTar)
		load := exec.Command("podman", "load", "-i", cacheTar)
		load.Stdout = os.Stderr
		load.Stderr = os.Stderr
		if loadErr := load.Run(); loadErr == nil {
			return image
		}
		t.Logf("WARNING: load from cache failed, rebuilding...")
	}

	// Slow path: ensure the base image is locally cached, then build from scratch.
	t.Logf("building fixture image %s (cache miss: %s)", image, cacheKey)
	ensureBaseImage(t, cfContent, cacheDir)
	// Use the parent directory (fixtures/) as build context so that files
	// shared across all fixtures (e.g. mock-jira-mcp.py) are accessible to
	// the Containerfile via COPY without path traversal.
	build := exec.Command("podman", "build", "-t", image, "-f", containerfile, filepath.Dir(containerfileDir))
	build.Stdout = os.Stderr
	build.Stderr = os.Stderr
	if err := build.Run(); err != nil {
		t.Fatalf("build fixture image %s: %v", image, err)
	}

	save := exec.Command("podman", "save", "-o", cacheTar, image)
	save.Stdout = os.Stderr
	save.Stderr = os.Stderr
	if saveErr := save.Run(); saveErr != nil {
		t.Logf("WARNING: could not cache fixture image: %v", saveErr)
	} else {
		t.Logf("fixture image cached: %s", cacheTar)
	}

	return image
}

// ensureBaseImage parses the FROM directive from cfContent and ensures that
// image is present in the local podman store. If not, it looks for a cached
// tarball in cacheDir (keyed by image name) before falling back to a pull.
// The tarball is saved on first pull so subsequent runs never hit the network
// for the base image.
func ensureBaseImage(t T, cfContent []byte, cacheDir string) {
	t.Helper()

	var baseImage string
	for _, line := range strings.Split(string(cfContent), "\n") {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(strings.ToUpper(trimmed), "FROM ") {
			parts := strings.Fields(trimmed)
			if len(parts) >= 2 {
				baseImage = parts[1]
				break
			}
		}
	}
	if baseImage == "" || strings.EqualFold(baseImage, "scratch") {
		return
	}

	if exec.Command("podman", "image", "exists", baseImage).Run() == nil {
		t.Logf("base image already in store: %s", baseImage)
		return
	}

	h := sha256.Sum256([]byte(baseImage))
	cacheTar := filepath.Join(cacheDir, "base-"+fmt.Sprintf("%x", h[:8])+".tar")

	if _, statErr := os.Stat(cacheTar); statErr == nil {
		t.Logf("loading base image from cache: %s → %s", cacheTar, baseImage)
		load := exec.Command("podman", "load", "-i", cacheTar)
		load.Stdout = os.Stderr
		load.Stderr = os.Stderr
		if loadErr := load.Run(); loadErr == nil {
			return
		}
		t.Logf("WARNING: load base image from cache failed, falling back to pull...")
	}

	t.Logf("pulling base image %s", baseImage)
	pull := exec.Command("podman", "pull", baseImage)
	pull.Stdout = os.Stderr
	pull.Stderr = os.Stderr
	if err := pull.Run(); err != nil {
		t.Logf("WARNING: pull base image %s: %v (build will attempt pull itself)", baseImage, err)
		return
	}

	save := exec.Command("podman", "save", "-o", cacheTar, baseImage)
	save.Stdout = os.Stderr
	save.Stderr = os.Stderr
	if saveErr := save.Run(); saveErr != nil {
		t.Logf("WARNING: could not cache base image tarball: %v", saveErr)
	} else {
		t.Logf("base image cached: %s", cacheTar)
	}
}

// StartFixtureContainer ensures the fixture image exists (building or loading
// from cache as needed), then starts a long-running container for the scenario.
//
// The container is started with:
//   - The outer workspace directory (parent of projectDir) mounted at the same
//     absolute path so that claude's relative ../skills/ path resolution works
//   - The AI workflows root mounted read-only at /workspace
//   - Per-scenario copy of ~/.claude for writable claude session state
//   - Read-only mounts for ~/.claude.json and ~/.config/gcloud if present
//   - Auth env vars forwarded (ANTHROPIC_API_KEY, Vertex AI vars)
//   - --privileged so Makefile targets can spawn their own containers
//   - Persistent nested podman storage at E2E_IMAGES_CACHE/nested-storage-{id}/
//     so images pulled by `make lint` etc. survive across fixture restarts
//
// A cleanup function is registered via t.Cleanup to stop the container.
func StartFixtureContainer(t T, s Scenario, projectDir string) *FixtureContainer {
	t.Helper()

	image := ensureFixtureImage(t, s)
	t.Logf("fixture image ready: %s", image)

	outerDir := filepath.Dir(projectDir)

	// Build podman run arguments.
	runArgs := []string{
		"run", "-d", "--rm",

		// Map uid 1000 in the fixture container to uid 1000 in the e2e
		// container (which owns the project directory and credential files).
		// This is required because rootless podman started from inside the
		// e2e container would otherwise remap uid 1000 to a subuid range,
		// making files owned by uid 1000 inaccessible to the e2e user.
		"--userns=keep-id",

		// Share the e2e container's network namespace so the fixture container
		// can reach services bound to localhost inside the e2e container —
		// most importantly, the per-scenario mock Jira MCP HTTP server started
		// by the test harness via httptest.NewServer.
		"--network=host",

		// Grant full Linux capabilities so the fixture container can start its
		// own containers (e.g. the golangci-lint image pulled by `make lint`,
		// or any other Makefile target that wraps a tool in a container).
		// Required for nested rootless podman to create user/mount namespaces.
		"--privileged",

		// Mount the outer workspace dir at the same absolute path so that
		// relative paths (../skills/controller.md) resolve identically inside
		// the container.
		"-v", outerDir + ":" + outerDir + ":z",

		// Mount the AI workflows root read-only so skills are accessible at
		// /workspace, the same path expected by AI_WORKFLOWS_ROOT.
		"-v", workspaceRoot() + ":/workspace:ro,z",

		// CWD inside the container is the project directory.
		"-w", projectDir,
	}

	// Persist the nested podman image store across fixture container restarts.
	// Without this, every run must re-pull images used by Makefile targets
	// (e.g. the golangci-lint container pulled by `make lint`). The cache dir
	// lives alongside the fixture image tarballs so it benefits from the same
	// E2E_IMAGES_CACHE volume mount in CI.
	nestedStorage := filepath.Join(fixtureImageCacheDir(), "nested-storage-"+s.ID)
	if err := os.MkdirAll(nestedStorage, 0o755); err != nil {
		t.Logf("WARNING: could not create nested storage cache dir %s: %v (nested pulls will not be cached)", nestedStorage, err)
	} else {
		runArgs = append(runArgs, "-v", nestedStorage+":/home/e2e/.local/share/containers/storage:z")
	}

	// Per-scenario writable copy of ~/.claude so claude can write session state
	// without conflicting with other concurrent scenarios.
	claudeDir := "/home/e2e/.claude"
	if _, err := os.Stat(claudeDir); err == nil {
		sessionCopy := filepath.Join(outerDir, "claude-session")
		if copyErr := copyDir(claudeDir, sessionCopy); copyErr != nil {
			t.Fatalf("copy claude session dir: %v", copyErr)
		}
		// Make the entire sessionCopy tree world-accessible. os.Chmod only sets
		// the top-level directory; nested dirs/files need the same treatment
		// so the fixture container's uid (different due to nested rootless
		// podman uid-namespace mapping) can read and write everything inside.
		chmodR(sessionCopy, 0o777, 0o666)
		runArgs = append(runArgs, "-v", sessionCopy+":/home/e2e/.claude:z")
	}

	// Credential files: copy to per-scenario temp paths and make world-readable
	// so that the fixture container's uid (which differs from the e2e
	// container's uid due to nested rootless podman uid-namespace mapping) can
	// still read them even though it doesn't own the files.
	if _, err := os.Stat("/home/e2e/.claude.json"); err == nil {
		claudeJSONCopy := filepath.Join(outerDir, "claude.json")
		if copyErr := copyFile("/home/e2e/.claude.json", claudeJSONCopy); copyErr == nil {
			os.Chmod(claudeJSONCopy, 0o644) //nolint:errcheck
			runArgs = append(runArgs, "-v", claudeJSONCopy+":/home/e2e/.claude.json:ro,z")
		}
	}
	if _, err := os.Stat("/home/e2e/.config/gcloud"); err == nil {
		gcloudCopy := filepath.Join(outerDir, "gcloud-config")
		if copyErr := copyDir("/home/e2e/.config/gcloud", gcloudCopy); copyErr == nil {
			chmodR(gcloudCopy, 0o755, 0o644) // dirs=755, files=644
			runArgs = append(runArgs, "-v", gcloudCopy+":/home/e2e/.config/gcloud:ro,z")
		}
	}

	// Forward auth env vars present in the e2e container.
	for _, key := range []string{
		"ANTHROPIC_API_KEY",
		"CLAUDE_CODE_USE_VERTEX",
		"ANTHROPIC_VERTEX_PROJECT_ID",
	} {
		if v := os.Getenv(key); v != "" {
			runArgs = append(runArgs, "-e", key+"="+v)
		}
	}

	runArgs = append(runArgs, image, "sleep", "infinity")

	run := exec.Command("podman", runArgs...)
	out, err := run.Output()
	if err != nil {
		t.Fatalf("start fixture container %s: %v", image, err)
	}
	id := strings.TrimSpace(string(out))

	// Copy the mock gh binary into outerDir/mock-bin/ so it is accessible
	// from inside the fixture container (outerDir is mounted at the same
	// path). mockGHBinDir() returns a path inside the e2e container that is
	// NOT mounted into the fixture container, so we must stage the binary.
	mockGHBinDst := filepath.Join(outerDir, "mock-bin")
	if err := os.MkdirAll(mockGHBinDst, 0o755); err != nil {
		t.Fatalf("create mock-bin dir: %v", err)
	}
	if err := copyFile(filepath.Join(mockGHBinDir(), "gh"), filepath.Join(mockGHBinDst, "gh")); err != nil {
		t.Fatalf("copy mock gh binary: %v", err)
	}
	if err := os.Chmod(filepath.Join(mockGHBinDst, "gh"), 0o755); err != nil {
		t.Fatalf("chmod mock gh: %v", err)
	}

	fc := &FixtureContainer{id: id, image: image, mockGHDir: mockGHBinDst}
	t.Cleanup(fc.stop)

	t.Logf("fixture container started: %s (image: %s)", id[:12], image)

	// Install ai-workflows slash commands for the Claude Code CLI so that
	// /implement:code and friends are discoverable inside this container.
	// The repo is already mounted read-only at /workspace; install.sh creates
	// a ~/.ai-workflows symlink → /workspace and populates ~/.claude/commands/.
	// Install ai-workflows slash commands for the Claude Code CLI so that
	// /implement:code and friends are discoverable inside this container.
	// The repo is already mounted read-only at /workspace; install.sh creates
	// a ~/.ai-workflows symlink → /workspace and populates ~/.claude/commands/.
	t.Logf("installing ai-workflows commands for claude CLI")
	fc.ExecAs(t, "e2e", "HOME=/home/e2e /workspace/install.sh claude")

	return fc
}

// workspaceRoot returns the AI workflows repo root. When AI_WORKFLOWS_ROOT is
// set (inside the e2e container) it is used directly; otherwise derived from
// the source file location.
func workspaceRoot() string {
	if root := os.Getenv("AI_WORKFLOWS_ROOT"); root != "" {
		return root
	}
	// Fallback for local runs without the env var.
	return "/workspace"
}

// RunClaude runs the claude CLI inside the fixture container via podman exec.
// It streams stdout/stderr to the provided writers (pass nil to discard).
// extraEnv is a map of additional env vars to forward as --env flags.
func (fc *FixtureContainer) RunClaude(workDir string, args []string, extraEnv map[string]string, stdout, stderr io.Writer) error {
	execArgs := []string{
		"exec",
		"--user", "e2e",
		"--env", "HOME=/home/e2e",
		// Ensure these are set even if the e2e container environment doesn't
		// carry them (they are baked into the fixture image but podman exec
		// --env flags override the container's own environment).
		"--env", "CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=1",
		"--env", "DISABLE_AUTOUPDATER=1",
		"--workdir", workDir,
	}

	// Strip auth tokens from the environment forwarded into the container;
	// pass the container-accessible mock gh directory as PATH prefix.
	for _, kv := range fc.safeEnvPairs(extraEnv) {
		execArgs = append(execArgs, "--env", kv)
	}

	execArgs = append(execArgs, fc.id, claudeBinInFixture)
	execArgs = append(execArgs, args...)

	cmd := exec.Command("podman", execArgs...)

	if stdout == nil {
		stdout = io.Discard
	}
	if stderr == nil {
		stderr = io.Discard
	}
	cmd.Stdout = stdout
	cmd.Stderr = stderr

	return cmd.Run()
}

// Exec runs a shell command in the fixture container and returns combined output.
// Fails the test if the command exits non-zero.
func (fc *FixtureContainer) Exec(t T, shellCmd string) string {
	t.Helper()
	cmd := exec.Command("podman", "exec", fc.id, "sh", "-c", shellCmd)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("exec %q in fixture container %s: %v\noutput:\n%s",
			shellCmd, fc.id[:12], err, out)
	}
	return string(out)
}

// ExecAs runs a shell command in the fixture container as the given user.
// Fails the test if the command exits non-zero.
func (fc *FixtureContainer) ExecAs(t T, user, shellCmd string) string {
	t.Helper()
	cmd := exec.Command("podman", "exec", "--user", user, fc.id, "sh", "-c", shellCmd)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("exec(user=%s) %q in fixture container %s: %v\noutput:\n%s",
			user, shellCmd, fc.id[:12], err, out)
	}
	return string(out)
}

// ExecWriter runs a shell command in the fixture container and streams output
// to w while also returning it. Fails the test if the command exits non-zero.
func (fc *FixtureContainer) ExecWriter(t T, shellCmd string, w io.Writer) string {
	t.Helper()

	if w == nil {
		w = io.Discard
	}

	cmd := exec.Command("podman", "exec", fc.id, "sh", "-c", shellCmd)

	var buf strings.Builder
	mw := io.MultiWriter(w, &buf)
	cmd.Stdout = mw
	cmd.Stderr = mw

	if err := cmd.Run(); err != nil {
		t.Fatalf("exec %q in fixture container %s: %v\noutput:\n%s",
			shellCmd, fc.id[:12], err, buf.String())
	}
	return buf.String()
}

// ID returns the container ID (for diagnostic messages).
func (fc *FixtureContainer) ID() string { return fc.id }

func (fc *FixtureContainer) stop() {
	if err := exec.Command("podman", "stop", "-t", "5", fc.id).Run(); err != nil {
		fmt.Fprintf(os.Stderr, "warning: stop fixture container %s: %v\n", fc.id[:12], err)
	}
}

// safeEnvPairs returns "KEY=VALUE" env strings safe to forward into the
// fixture container. It prepends fc.mockGHDir — the path to the mock gh
// binary as seen from INSIDE the container — to PATH, and strips auth tokens.
func (fc *FixtureContainer) safeEnvPairs(extraEnv map[string]string) []string {
	stripped := map[string]bool{
		"GH_TOKEN":            true,
		"GITHUB_TOKEN":        true,
		"GH_ENTERPRISE_TOKEN": true,
	}

	var pairs []string
	for _, kv := range os.Environ() {
		k := strings.SplitN(kv, "=", 2)[0]
		if stripped[k] {
			continue
		}
		if k == "PATH" {
			v := strings.SplitN(kv, "=", 2)[1]
			pairs = append(pairs, "PATH="+fc.mockGHDir+string(os.PathListSeparator)+v)
			continue
		}
		pairs = append(pairs, kv)
	}
	for k, v := range extraEnv {
		pairs = append(pairs, k+"="+v)
	}
	return pairs
}

// copyDir copies src directory tree to dst using cp -a.
func copyDir(src, dst string) error {
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return fmt.Errorf("mkdir %s: %w", dst, err)
	}
	var buf bytes.Buffer
	cmd := exec.Command("cp", "-a", src+"/.", dst)
	cmd.Stdout = &buf
	cmd.Stderr = &buf
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("cp -a %s → %s: %w\n%s", src, dst, err, buf.String())
	}
	return nil
}

// copyFile copies a single file from src to dst.
func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

// chmodR recursively sets dirMode on directories and fileMode on files under root.
func chmodR(root string, dirMode, fileMode os.FileMode) {
	filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
		if err != nil {
			return nil
		}
		if d.IsDir() {
			os.Chmod(path, dirMode) //nolint:errcheck
		} else {
			os.Chmod(path, fileMode) //nolint:errcheck
		}
		return nil
	})
}
