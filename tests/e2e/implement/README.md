# E2E Tests — implement skill

End-to-end tests that run the real `claude` CLI through every phase of the
`implement` skill against a real-world codebase, then assert that the produced
artifacts and code meet structural and quality standards.

---

## Container topology

Tests run in two layers of containers. The outer layer provides a consistent,
reproducible Go test harness; the inner layer provides the exact build toolchain
and the `claude` CLI, mirroring a real developer's environment.

```
Host machine
└── run-e2e.sh  (podman run --privileged)
    └── e2e container  [Containerfile]
        │  Go harness (Ginkgo specs)
        │  git
        │  podman (nested, daemonless)
        │
        └── fixture container  [fixtures/{ID}/Containerfile]
               Starts once per test, before the first phase
               claude CLI runs here via "podman exec --user e2e claude ..."
               projectDir mounted at its e2e-container path (read-write)
               /workspace mounted read-only (implement skills)
               ~/.claude session copy mounted (per-scenario, writable)
               make build, make unit-test, go test ... all run here too
               Stopped by t.Cleanup at the end of the test
```

### e2e container (`Containerfile`)

Built from `registry.access.redhat.com/ubi9/go-toolset` and contains only
what the Go harness itself needs:

| Tool | Purpose |
|------|---------|
| Go | Compile and run the Ginkgo test harness |
| git | Clone fixture repos into the cache |
| podman | Build and run fixture containers |

The container runs as a non-root user (`e2e`, UID 1000). It does **not**
contain the `claude` CLI — that lives inside the fixture container alongside
the project build tools.

### fixture container (`fixtures/{ID}/Containerfile`)

Every scenario must ship a `Containerfile` at `fixtures/{ID}/Containerfile`.
It is built once per test run (layer cache keeps rebuilds fast), and a single
long-running instance is started per test case **before the first phase begins**.

The fixture container is responsible for:

- **The project build environment** — e.g. `libvirt-devel`, `pam-devel`, `protoc`
  for flightctl. All `BuildConfig` commands (`Compile`, `Test`, `CoverageCmd`)
  run here via `podman exec`.
- **The `claude` CLI** — installed as the `e2e` user (UID 1000) so that
  `RunPhase` calls execute `podman exec --user e2e claude /implement:<phase>`.
  This means claude runs in the same environment as the build tools, so TDD
  attempts (`make build`, `make unit-test`) succeed immediately without wrappers.

The fixture image is cached to `~/.cache/e2e-fixture-images/` as a tarball
keyed by the SHA-256 of the Containerfile content. An advisory file lock
prevents concurrent scenarios from racing on the same image build.

---

## Credential flow

```
Host ~/.claude
    │
    └──(run-e2e.sh copies to tmp)──▶ e2e container /home/e2e/.claude
                                                    │
                           fixture_container.go copies to outerDir/claude-session/
                                                    │
                                  podman run -v outerDir/claude-session:/home/e2e/.claude
                                                    │
                                          fixture container
                                          (claude writes session state here)
```

Each scenario gets its **own copy** of the claude session directory so
concurrent Ginkgo nodes cannot corrupt each other's session state.

`ANTHROPIC_API_KEY` (CI) and Vertex AI env vars (`CLAUDE_CODE_USE_VERTEX`,
`ANTHROPIC_VERTEX_PROJECT_ID`) are forwarded from `run-e2e.sh` → e2e container
→ fixture container as `--env` flags on `podman run`.

---

## Fixture structure

```
fixtures/
└── {SCENARIO-ID}/
    ├── Containerfile          # Build environment + claude CLI for this fixture
    ├── stories/
    │   ├── {STORY-KEY}.json   # Mock Jira MCP response for the primary story
    │   ├── {PARENT-KEY}.json  # …and any linked stories the skill may fetch
    │   └── ...
    ├── docs-repo/
    │   └── main/
    │       └── {feature}/
    │           ├── design.md  # PRD / design doc referenced by /ingest
    │           └── prd.md
    └── artifacts/
        ├── 01-context.md      # Pre-seeded /ingest output (used by /plan tests)
        └── 02-plan.md         # Pre-seeded /plan output (used by /code tests)
```

### `stories/*.json`

Returned verbatim by the mock Jira MCP server (`StartMockMCP`) when the skill
fetches a story by key. The filename is `{KEY}.json` (e.g. `EDM-3895.json`).

### `artifacts/`

Pre-generated outputs from earlier phases. Phase-specific tests seed these
files into the project directory before running the phase under test so that
each test can start from a known state without running the preceding phases.

### `Containerfile`

Defines the build environment **and** installs the `claude` CLI. Base the image
on whichever image the target project uses for its own CI builds, then add:

```dockerfile
RUN useradd -m -u 1000 e2e
USER e2e
ENV HOME=/home/e2e
RUN curl -fsSL https://claude.ai/install.sh | sh \
    && chmod -R a+rX /home/e2e/.local
ENV PATH=/home/e2e/.local/bin:$PATH \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS=1
```

---

## Scenario definition

Scenarios are plain Go structs in [`scenarios_test.go`](scenarios_test.go).
Add a new scenario by appending to `allScenarios`:

```go
var allScenarios = []harness.Scenario{
    {
        ID:       "EDM-3895",
        StoryKey: "EDM-3895",
        Repo: harness.RepoConfig{
            URL:        "https://github.com/flightctl/flightctl",
            PreFixSHA:  "8abf88fa2",   // checkout without the feature (agent starts here)
            PostFixSHA: "adcf70ee5",   // checkout with the real implementation (reference)
        },
        Build: harness.BuildConfig{
            Compile:           "make build",
            Test:              "make unit-test",
            CoverageCmd:       "make unit-test",
            CoverageThreshold: 80,
        },
        // ... assertions, token budgets, etc.
    },
}
```

`Build` commands run inside the fixture container via `podman exec`. Keep them
simple — the Containerfile takes care of the environment.

---

## Running the tests

### Locally

```bash
# All tests (builds both images on first run; fixture image is cached)
tests/e2e/implement/run-e2e.sh

# Single phase
tests/e2e/implement/run-e2e.sh --focus="ingest phase"

# Full workflow end-to-end
tests/e2e/implement/run-e2e.sh --focus="full workflow"

# One scenario
tests/e2e/implement/run-e2e.sh --focus="EDM-3895"
```

Authentication uses your local `claude login` session. `run-e2e.sh` copies
`~/.claude` into a writable temp directory, mounts it into the e2e container,
and the harness copies it again (per-scenario) into each fixture container.
Set `ANTHROPIC_API_KEY` if you prefer API-key auth instead.

For Vertex AI authentication, ensure `CLAUDE_CODE_USE_VERTEX`,
`ANTHROPIC_VERTEX_PROJECT_ID`, and `~/.config/gcloud` are present — they are
forwarded automatically.

### In CI

CI calls the same script:

```yaml
- name: Run e2e tests
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: tests/e2e/implement/run-e2e.sh --timeout 90m
```

No Go, Ginkgo, or claude CLI setup is needed on the CI host — the script
builds and runs everything inside the containers.

---

## Adding a new scenario

1. Create `fixtures/{NEW-ID}/` with the required sub-directories.
2. Write `fixtures/{NEW-ID}/Containerfile` for the project's build environment,
   including the `e2e` user and claude CLI install (see template above).
3. Place mock Jira JSON files in `fixtures/{NEW-ID}/stories/`.
4. Generate (or copy) `artifacts/01-context.md` and `02-plan.md` for phase
   isolation tests.
5. Append a `harness.Scenario{}` to `allScenarios` in `scenarios_test.go`.
6. Run `run-e2e.sh --focus="{NEW-ID}"` to validate locally.

---

## Harness internals

| File | Responsibility |
|------|---------------|
| `harness/scenario.go` | `Scenario` struct and all config types |
| `harness/fixture_container.go` | `FixtureContainer` — build image, start/stop, `RunClaude` (via `podman exec`), `Exec` |
| `harness/repo_cache.go` | Blobless clone cache, `PrepareRepo`, `SeedArtifacts` |
| `harness/cli_runner.go` | `RunPhase` — delegates to `fc.RunClaude` (fixture container) or local exec, streams output, tracks tokens |
| `harness/mock_mcp.go` | In-process HTTP server serving story JSON for `/ingest` |
| `harness/assertions.go` | Per-phase assertion helpers |
| `harness/code_reviewer.go` | LLM-based comparison report with quality scores and per-phase token usage (informational, never fails) |
| `mock_gh/main.go` | Compiled to `fixtures/bin/gh`, intercepts `gh pr create` calls |
