package harness

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// minimumPhaseDuration is the shortest plausible wall-clock time for a real
// LLM response. A run faster than this almost certainly means claude exited
// immediately (not authenticated, binary missing, etc.).
const minimumPhaseDuration = 3 * time.Second

// defaultClaudeBin is the path used when running claude locally (outside the
// fixture container). It matches the path used in the e2e Containerfile when
// claude is installed as the e2e user.
// Override with CLAUDE_BIN for local runs where the path differs.
const defaultClaudeBin = "/home/e2e/.local/bin/claude"

// claudeBin returns the path to the claude CLI binary (unexported, for harness use).
func claudeBin() string { return ClaudeBin() }

// ClaudeBin returns the path to the claude CLI binary.
// Exported so suite_test.go can use the same resolution logic.
func ClaudeBin() string {
	if v := os.Getenv("CLAUDE_BIN"); v != "" {
		return v
	}
	return defaultClaudeBin
}

// RunResult captures the output of one claude CLI invocation.
type RunResult struct {
	Stdout     string
	Stderr     string
	ExitCode   int
	TokensUsed TokenUsage
	Duration   time.Duration
}

// TokenUsage holds the token counts extracted from claude's JSON output.
type TokenUsage struct {
	InputTokens  int `json:"input_tokens"`
	OutputTokens int `json:"output_tokens"`
	CacheRead    int `json:"cache_read_input_tokens"`
	CacheWrite   int `json:"cache_creation_input_tokens"`
}

// streamEvent is one newline-delimited JSON object from --output-format stream-json.
type streamEvent struct {
	Type    string     `json:"type"`
	Subtype string     `json:"subtype"`
	Result  string     `json:"result"`
	Usage   TokenUsage `json:"usage"`
	// For assistant/user messages
	Message struct {
		Role    string `json:"role"`
		Content []struct {
			Type  string `json:"type"`
			Text  string `json:"text"`
			Name  string `json:"name"`  // tool_use: tool name
			Input any    `json:"input"` // tool_use: arguments
		} `json:"content"`
	} `json:"message"`
	// For system init
	Model   string   `json:"model"`
	Tools   []string `json:"tools"`
	MCPSrvs []struct {
		Name   string `json:"name"`
		Status string `json:"status"`
	} `json:"mcp_servers"`
}

// streamFilterWriter wraps an io.Writer and translates claude's stream-json
// events into compact human-readable lines. The full raw JSON is NOT forwarded;
// callers that need raw bytes (e.g. token counting) should tee before wrapping.
type streamFilterWriter struct {
	w   io.Writer
	buf bytes.Buffer
}

func newStreamFilterWriter(w io.Writer) *streamFilterWriter { return &streamFilterWriter{w: w} }

func (f *streamFilterWriter) Write(p []byte) (int, error) {
	f.buf.Write(p) //nolint:errcheck
	for {
		line, err := f.buf.ReadString('\n')
		if err != nil {
			// incomplete line — put it back
			f.buf.WriteString(line) //nolint:errcheck
			break
		}
		f.emitLine(strings.TrimRight(line, "\n\r"))
	}
	return len(p), nil
}

func (f *streamFilterWriter) emitLine(line string) {
	line = strings.TrimSpace(line)
	if line == "" {
		return
	}
	var ev streamEvent
	if err := json.Unmarshal([]byte(line), &ev); err != nil {
		// Not JSON (e.g. stderr) — pass through as-is.
		fmt.Fprintln(f.w, line) //nolint:errcheck
		return
	}
	switch ev.Type {
	case "system":
		if ev.Subtype == "init" {
			var mcpNames []string
			for _, s := range ev.MCPSrvs {
				mcpNames = append(mcpNames, s.Name+"("+s.Status+")")
			}
			mcp := "none"
			if len(mcpNames) > 0 {
				mcp = strings.Join(mcpNames, ", ")
			}
			fmt.Fprintf(f.w, "[claude] model=%s mcp=%s\n", ev.Model, mcp) //nolint:errcheck
		}
	case "assistant":
		for _, c := range ev.Message.Content {
			switch c.Type {
			case "text":
				if t := strings.TrimSpace(c.Text); t != "" {
					fmt.Fprintln(f.w, t) //nolint:errcheck
				}
			case "tool_use":
				// Print a brief one-liner summarising the tool call.
				inputJSON, _ := json.Marshal(c.Input)
				summary := string(inputJSON)
				if len(summary) > 120 {
					summary = summary[:120] + "…"
				}
				fmt.Fprintf(f.w, "  → %s %s\n", c.Name, summary) //nolint:errcheck
			}
		}
	case "result":
		u := ev.Usage
		fmt.Fprintf(f.w, "[claude] done  input=%d output=%d cache_read=%d\n",
			u.InputTokens, u.OutputTokens, u.CacheRead) //nolint:errcheck
	}
	// user events (tool results) and other types are silently dropped.
}

// phaseMaxTurns returns the --max-turns cap for the named phase.
//
// In production the model is interactive: the user's presence acts as a
// natural throttle — the model reads the minimum necessary files, writes its
// artifact, and stops. In --print (unattended) mode there is no such signal,
// so the model can consume all 60 default turns exploring the codebase before
// synthesizing, causing Anthropic's server-side per-request timeout.
//
// These limits are set to ~2× the observed production turn counts so tests
// remain robust without allowing runaway exploration.
func phaseMaxTurns(phase string) int {
	switch phase {
	case "ingest":
		return 40 // observed: ~30 turns at up to 8s/turn as cache grows
	case "plan":
		return 40
	case "validate":
		return 60 // many steps; each turn may include a compilation/test run
	case "publish":
		return 40
	case "code":
		return 100 // TDD loops + each turn may include a compilation step
	default:
		return 40
	}
}

// phaseBudget returns the token budget for the named phase.
func phaseBudget(s Scenario, phase string) int {
	switch phase {
	case "ingest":
		return s.TokenBudgets.Ingest
	case "plan":
		return s.TokenBudgets.Plan
	case "code":
		return s.TokenBudgets.Code
	case "validate":
		return s.TokenBudgets.Validate
	case "publish":
		return s.TokenBudgets.Publish
	}
	return 0
}

// mockGHBinDir returns the absolute path to the fixtures/bin/ directory.
func mockGHBinDir() string {
	_, file, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(file), "..", "fixtures", "bin")
}

// safeEnv returns a copy of the current environment with auth tokens stripped
// and the mock gh binary directory prepended to PATH.
func safeEnv(extraEnv map[string]string) []string {
	stripped := map[string]bool{
		"GH_TOKEN":            true,
		"GITHUB_TOKEN":        true,
		"GH_ENTERPRISE_TOKEN": true,
	}

	var env []string
	for _, kv := range os.Environ() {
		k := strings.SplitN(kv, "=", 2)[0]
		if stripped[k] {
			continue
		}
		if k == "PATH" {
			v := strings.SplitN(kv, "=", 2)[1]
			env = append(env, "PATH="+mockGHBinDir()+string(os.PathListSeparator)+v)
			continue
		}
		env = append(env, kv)
	}

	for k, v := range extraEnv {
		env = append(env, k+"="+v)
	}
	return env
}

// formatRunError builds a diagnostic message that includes all available context.
func formatRunError(phase string, result RunResult, extra string) string {
	var sb strings.Builder
	fmt.Fprintf(&sb, "claude /implement:%s failed\n", phase)
	fmt.Fprintf(&sb, "  exit code : %d\n", result.ExitCode)
	fmt.Fprintf(&sb, "  duration  : %s\n", result.Duration.Round(time.Millisecond))
	if result.Stderr != "" {
		fmt.Fprintf(&sb, "  stderr    :\n%s\n", indent(result.Stderr, "    "))
	}
	if result.Stdout != "" {
		preview := result.Stdout
		if len(preview) > 2000 {
			preview = preview[:2000] + "\n... (truncated)"
		}
		fmt.Fprintf(&sb, "  stdout    :\n%s\n", indent(preview, "    "))
	}
	if extra != "" {
		fmt.Fprintf(&sb, "  note      : %s\n", extra)
	}
	return sb.String()
}

func indent(s, prefix string) string {
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	for i, l := range lines {
		lines[i] = prefix + l
	}
	return strings.Join(lines, "\n")
}

// RunPhase invokes claude with --output-format stream-json so events are
// streamed to w (pass GinkgoWriter for live test output) while also being
// buffered for post-run inspection and token-usage parsing.
//
// When fc is non-nil, the claude CLI is executed inside the fixture container
// via podman exec (the normal production path). When fc is nil, the CLI is
// executed locally using ClaudeBin() — useful for local development outside
// the container topology.
//
// Fails immediately (via t.Fatalf) if:
//   - claude is not found (local path) or podman exec fails to start
//   - the process exits non-zero
//   - it completes faster than minimumPhaseDuration (no real API call made)
func RunPhase(t T, phase, projectDir string, s Scenario, fc *FixtureContainer, extraEnv map[string]string, w io.Writer) RunResult {
	t.Helper()

	if w == nil {
		w = io.Discard
	}

	// Allow callers to override the per-phase timeout via PHASE_TIMEOUT_MINUTES.
	timeoutMin := 20
	if v := os.Getenv("PHASE_TIMEOUT_MINUTES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			timeoutMin = n
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutMin)*time.Minute)
	defer cancel()

	// If the caller provided a Jira mock URL, write a .mcp.json into the
	// project directory so the ingest skill can use the MCP tool calls.
	if jiraURL, ok := extraEnv["JIRA_MCP_URL"]; ok && jiraURL != "" {
		writeMCPConfig(t, projectDir, jiraURL)
	}

	// Commands are namespaced as /implement:{phase} — matching the frontmatter
	// `name: implement:{phase}` in the workflow's commands/*.md files.
	prompt := fmt.Sprintf("/implement:%s %s", phase, s.StoryKey)
	// --dangerously-skip-permissions is always required in the test environment
	// so claude can read skill files without interactive approval.  The env-var
	// guard was previously wrong: CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS lives in
	// the fixture container image, not in the e2e container where this code runs.
	//
	// Per-phase max-turns budget: in production the user's presence acts as an
	// implicit throttle — the model reads a few files, writes the artifact, and
	// stops. In --print mode (no human waiting) the model explores much more
	// broadly, accumulating millions of cached tokens before synthesizing, which
	// triggers the Anthropic server-side per-request timeout. Tighter limits
	// match observed production turn counts and prevent runaway exploration.
	maxTurns := phaseMaxTurns(phase)
	claudeArgs := []string{
		"--print", "--verbose", "--output-format", "stream-json",
		"--max-turns", strconv.Itoa(maxTurns),
		"--dangerously-skip-permissions",
	}
	claudeArgs = append(claudeArgs, prompt)

	var outBuf bytes.Buffer
	var errBuf bytes.Buffer

	start := time.Now()
	var cmdErr error

	if fc != nil {
		// Production path: run claude inside the fixture container via podman exec.
		// Raw JSON → outBuf (for token counting); filtered human-readable → w.
		filter := newStreamFilterWriter(w)
		outW := io.MultiWriter(filter, &outBuf)
		errW := io.MultiWriter(w, &errBuf)

		// Wrap the context deadline: RunClaude does not accept a context directly,
		// so we use a goroutine to kill the container exec on timeout.
		done := make(chan error, 1)
		go func() {
			done <- fc.RunClaude(projectDir, claudeArgs, extraEnv, outW, errW)
		}()
		select {
		case cmdErr = <-done:
		case <-ctx.Done():
			cmdErr = fmt.Errorf("phase timeout after %d minutes", timeoutMin)
		}
	} else {
		// Local fallback: run claude directly.
		claudePath := ClaudeBin()
		if _, err := os.Stat(claudePath); err != nil {
			t.Fatalf("claude CLI not found at %s (local mode — set CLAUDE_BIN or use the fixture container)",
				claudePath)
		}
		cmd := exec.CommandContext(ctx, claudePath, claudeArgs...)
		cmd.Dir = projectDir
		cmd.Env = safeEnv(extraEnv)
		filter := newStreamFilterWriter(w)
		cmd.Stdout = io.MultiWriter(filter, &outBuf)
		cmd.Stderr = io.MultiWriter(w, &errBuf)
		cmdErr = cmd.Run()
	}

	elapsed := time.Since(start)

	result := RunResult{
		Duration: elapsed,
		Stdout:   outBuf.String(),
		Stderr:   errBuf.String(),
	}

	if cmdErr != nil {
		if exitErr, ok := cmdErr.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
		}
		t.Fatalf(formatRunError(phase, result,
			fmt.Sprintf("%v — check API key and network connectivity", cmdErr)))
	}

	// A real LLM invocation always takes several seconds.
	if elapsed < minimumPhaseDuration {
		t.Fatalf(formatRunError(phase, result, fmt.Sprintf(
			"claude completed in %s which is below the minimum expected duration (%s).\n"+
				"This usually means claude exited without making an API call.\n"+
				"Check: (1) ANTHROPIC_API_KEY is set and valid, "+
				"(2) credentials are mounted into the fixture container.",
			elapsed.Round(time.Millisecond), minimumPhaseDuration)))
	}

	// Parse token usage from the final "result" event in the stream.
	for _, line := range strings.Split(result.Stdout, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var ev streamEvent
		if jsonErr := json.Unmarshal([]byte(line), &ev); jsonErr != nil {
			continue
		}
		if ev.Type == "result" {
			result.TokensUsed = ev.Usage
			break
		}
	}

	// Warn (never fail) on token budget overrun.
	if budget := phaseBudget(s, phase); budget > 0 {
		total := result.TokensUsed.InputTokens + result.TokensUsed.OutputTokens
		if total > budget {
			t.Logf("WARNING: /implement:%s used %d tokens (budget %d)", phase, total, budget)
		} else if total > 0 {
			t.Logf("/implement:%s tokens: input=%d output=%d cache_read=%d (budget %d)",
				phase,
				result.TokensUsed.InputTokens,
				result.TokensUsed.OutputTokens,
				result.TokensUsed.CacheRead,
				budget)
		}
	}

	return result
}

// writeMCPConfig writes a .mcp.json to projectDir configuring the mock Jira
// MCP server. The server script (/usr/local/bin/mock-jira-mcp) is installed in
// the fixture image and speaks JSON-RPC 2.0 over stdio, forwarding tool calls
// to the HTTP mock at jiraURL.
func writeMCPConfig(t T, projectDir, jiraURL string) {
	t.Helper()
	cfg := fmt.Sprintf(`{
  "mcpServers": {
    "jira": {
      "command": "/usr/local/bin/mock-jira-mcp",
      "env": {
        "JIRA_MCP_URL": %q
      }
    }
  }
}`, jiraURL)
	p := filepath.Join(projectDir, ".mcp.json")
	if err := os.WriteFile(p, []byte(cfg), 0o644); err != nil {
		t.Fatalf("write .mcp.json: %v", err)
	}
	t.Logf("wrote Jira MCP config: %s → %s", p, jiraURL)
}
