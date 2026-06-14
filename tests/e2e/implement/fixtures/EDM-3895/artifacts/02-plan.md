# Implementation Plan — EDM-3895

## Summary

Create `internal/restore/archive.go` with three focused functions (extract,
read metadata, validate deployment type), then update `cmd/flightctl-restore/main.go`
to accept a required positional archive path argument and wire the new archive
functions into the existing restore flow — before the existing DB/KV init and
`PrepareDevices` call.

## Branch

- **Name:** EDM-3895-restore-archive-argument
- **Base:** EDM-3885 (epic integration branch; includes EDM-3892 backup work that defines `backup.BackupMetadata`)

## Interface Definitions

### New Types

No new types. `backup.BackupMetadata` and `backup.DeploymentType` are reused
from `internal/backup` (no changes to that package).

### Modified Interfaces

None.

### New Functions

```go
// In internal/restore/archive.go

// ExtractArchive validates that archivePath exists and is a readable regular
// file, then extracts the tar.gz to a new temporary directory. Returns the
// path to the extracted directory. Caller is responsible for cleanup via
// os.RemoveAll. Returns a non-empty extractDir ONLY on success; on error,
// extractDir is always "".
func ExtractArchive(ctx context.Context, archivePath string) (extractDir string, err error)

// ReadMetadata reads and unmarshals metadata.json from the root of an
// extracted archive directory. Returns an error if the file is missing or
// contains invalid JSON.
func ReadMetadata(extractDir string) (*backup.BackupMetadata, error)

// ValidateDeploymentType checks that the archive's recorded deployment type
// matches the caller-supplied current environment type. Returns a descriptive
// error on mismatch; nil on match.
func ValidateDeploymentType(metadata *backup.BackupMetadata, currentType backup.DeploymentType) error
```

### Updated Function Signature

```go
// In cmd/flightctl-restore/main.go
// archivePath is the required first positional argument.
func runRestore(ctx context.Context, archivePath string) error
```

## Key Design Decisions

**OQ-1: Cross-package dependency (restore → backup)**
`internal/restore/archive.go` will import `internal/backup` for
`BackupMetadata` and `DeploymentType`. This is acceptable — there is no
circular dependency (backup never imports restore). Deployment type detection
is done in `runRestore` by calling `backup.DetectDeployment(cfg, log, "")` and
passing `deployer.Type()` into `ValidateDeploymentType`. This keeps detection
logic in one place (no duplication) while keeping `archive.go` functions
pure and highly testable.

**OQ-2: Required vs optional archive path**
`cobra.ExactArgs(1)` — Cobra produces clear error messages for 0 or >1 args.
No custom argument validation needed. AC-1 is satisfied entirely by Cobra.

**Cleanup safety**
`ExtractArchive` returns `("", err)` on failure and `(path, nil)` on success
(never both). In `runRestore`, cleanup is:
```go
extractDir, err := restore.ExtractArchive(ctx, archivePath)
defer func() {
    if extractDir != "" {
        os.RemoveAll(extractDir)
    }
}()
```
This guarantees cleanup on any subsequent failure path (AC-8) while being
safe if extraction itself failed.

**Order of operations in `runRestore`**
Archive validation is done early (before expensive DB/KV/tracer init) to
fail fast:
1. Load config
2. Init logging
3. Extract archive + defer cleanup
4. Read metadata
5. Detect current deployment type (`backup.DetectDeployment`)
6. Validate deployment type
7. Init tracer
8. Init DB
9. Init KV
10. `restore.PrepareDevices` (existing logic, unchanged)

## Test Strategy

### Unit Tests

#### internal/restore (archive_test.go)

- **Test file:** `internal/restore/archive_test.go`
- **Package:** `package restore` (whitebox, matching backup_test.go pattern)
- **Test pattern:** Table-driven (`t.Run` with "When ... it should ..." names)
- **Mocks needed:** None — pure file I/O; tests create real tar.gz fixtures

**`TestExtractArchive`**
| Case | Expected |
|------|----------|
| Valid `.tar.gz` with `metadata.json` | Returns populated extractDir, nil error |
| Path does not exist | Returns `""`, error containing "no such file" or similar |
| Path is a directory | Returns `""`, error indicating not a regular file |
| Path exists but contains invalid gzip | Returns `""`, error on extraction |
| Context already cancelled | Returns `""`, context error |

**`TestReadMetadata`**
| Case | Expected |
|------|----------|
| Valid `metadata.json` with all fields | Returns correctly populated `*BackupMetadata` |
| `metadata.json` missing from dir | Returns nil, error |
| `metadata.json` contains invalid JSON | Returns nil, error |
| `metadata.json` has unknown `deploymentType` | Parses successfully (no validation here) |

**`TestValidateDeploymentType`**
| Case | Expected |
|------|----------|
| Archive type `"podman"`, current `"podman"` | nil |
| Archive type `"kubernetes"`, current `"kubernetes"` | nil |
| Archive type `"podman"`, current `"kubernetes"` | Error mentioning both types |
| Archive type `"kubernetes"`, current `"podman"` | Error mentioning both types |
| Archive type `"unknown"` | Error (unknown cannot match) |

### Integration Tests

No integration tests required — this story does not touch component
interactions (DB, KV, API). All logic is pure file I/O.

### Coverage Goals

All behavioral paths through the three public functions are exercised via
unit tests. The error paths in `ExtractArchive` (file-not-found, not-a-file,
bad gzip, context cancellation) are each a separate table row. The main.go
wiring is exercised indirectly by the unit tests on archive functions.

## Task Breakdown

### Task 1: Create `internal/restore/archive.go`

- **Files:** `internal/restore/archive.go`
- **What:**
  - Add package imports: `archive/tar`, `compress/gzip`, `context`, `encoding/json`,
    `fmt`, `io`, `os`, `path/filepath`, and `github.com/flightctl/flightctl/internal/backup`
  - Implement `ExtractArchive`: stat the path (fail if missing or not a regular file),
    create temp dir via `os.MkdirTemp("", "flightctl-restore-*")`, open gzip reader,
    open tar reader, walk entries extracting files and directories with safe path
    validation (no `../` traversal), return temp dir path on success
  - Implement `ReadMetadata`: read `metadata.json` from `filepath.Join(extractDir, "metadata.json")`,
    unmarshal into `backup.BackupMetadata`, return pointer
  - Implement `ValidateDeploymentType`: compare `metadata.DeploymentType` with
    `currentType`; return formatted error on mismatch naming both types
- **Why:** AC-3 (extract), AC-4 (read metadata), AC-5 (validate), AC-6 (mismatch error), AC-7 (path error), AC-8 (caller cleanup contract)
- **Commit message:** `EDM-3895: Add archive extraction and metadata validation to restore package`
- **Status:** Done (commit 2e24d13f1)

### Task 2: Add unit tests `internal/restore/archive_test.go`

- **Files:** `internal/restore/archive_test.go`
- **What:**
  - Helper `buildTestArchive(t, files map[string]string) string` — creates a real
    `.tar.gz` in a temp dir using `archive/tar` + `compress/gzip`, returns the archive
    path. Used by `TestExtractArchive` and `TestReadMetadata`.
  - `TestExtractArchive` — table-driven, covers all cases listed in test strategy
  - `TestReadMetadata` — table-driven, creates archives with various `metadata.json`
    content (valid, missing, malformed JSON)
  - `TestValidateDeploymentType` — table-driven, covers all match/mismatch combinations
- **Why:** AC-9 (unit tests covering argument parsing, extraction, metadata validation)
- **Commit message:** (included in Task 1 commit — single logical commit)
- **Status:** Done (commit 2e24d13f1)

### Task 3: Update `cmd/flightctl-restore/main.go`

- **Files:** `cmd/flightctl-restore/main.go`
- **What:**
  - Change `Use` to `"flightctl-restore <archive-path> [flags]"`
  - Change `Short`/`Long` to describe the new archive-based restore workflow
  - Add `Args: cobra.ExactArgs(1)` to the command struct
  - Update `RunE` to pass `args[0]` to `runRestore`
  - Update `runRestore` signature to `func runRestore(ctx context.Context, archivePath string) error`
  - Add `log.Printf("Restoring from archive: %s", archivePath)` early in `runRestore` (AC-2)
  - Call `restore.ExtractArchive(ctx, archivePath)` after config+logging init; set up `defer` cleanup
  - Call `restore.ReadMetadata(extractDir)`
  - Call `backup.DetectDeployment(cfg, log, "")` to get current deployment type
  - Call `restore.ValidateDeploymentType(metadata, deployer.Type())`
  - Keep existing tracer, DB, KV init and `restore.PrepareDevices` call unchanged
  - Add import `"github.com/flightctl/flightctl/internal/backup"` and `"os"`
- **Why:** AC-1 (accept archive arg), AC-2 (log archive path), AC-3/4/5/6/7/8 (wired via archive.go functions)
- **Commit message:** `EDM-3895: Enhance flightctl-restore to accept and process backup archive argument`
- **Status:** Done (commit 6476ee9d0)

## Acceptance Criteria Coverage

| AC | Description | Covered by |
|----|-------------|------------|
| AC-1 | Accepts archive path as first positional argument | Task 3 (`cobra.ExactArgs(1)`) |
| AC-2 | Logs archive path when provided | Task 3 (`runRestore` log line) |
| AC-3 | Extracts archive to temporary directory | Task 1 (`ExtractArchive`), Task 3 (wired) |
| AC-4 | Reads `metadata.json` from extracted archive | Task 1 (`ReadMetadata`), Task 3 (wired) |
| AC-5 | Validates deployment type matches current environment | Task 1 (`ValidateDeploymentType`), Task 3 (wired) |
| AC-6 | Fails with clear error on deployment type mismatch | Task 1 (`ValidateDeploymentType` error message) |
| AC-7 | Fails with clear error if path does not exist or not readable | Task 1 (`ExtractArchive` stat check) |
| AC-8 | Temp dir cleaned up on success or failure | Task 1 (contract), Task 3 (defer cleanup) |
| AC-9 | Unit tests: argument parsing, extraction, metadata validation | Task 2 |

All acceptance criteria are covered. No gaps.

## Risk Assessment

- **`backup` → `restore` import direction confusion:** Low risk. The dependency is
  `restore` → `backup` (restore imports backup for shared types). No circular dependency.
  Mitigation: Verified — `internal/backup` has no imports of `internal/restore`.

- **Tar path traversal vulnerability:** Medium risk in `ExtractArchive`. When extracting
  user-supplied archives, a malicious archive could include `../` paths. Mitigation:
  validate each extracted path with `filepath.Clean` and confirm it is rooted within
  the temp dir before writing.

- **`os.RemoveAll("")` safety:** Would remove the working directory. Mitigation: the
  cleanup guard `if extractDir != ""` in `runRestore`'s defer is mandatory.

- **`backup.DetectDeployment` behavior in test environments:** In CI, neither Podman
  nor Kubernetes indicators may be present, so `DetectDeployment` may return an error.
  This is a runtime concern for `runRestore`, not for unit tests (which test archive
  functions in isolation). Not a blocker for this story.

## Open Questions

None remaining — all planning questions resolved above.
