# Story Context — EDM-3895

## Story Summary

- **Title:** [DEV] Enhance flightctl-restore to accept backup archive argument
- **Type:** [DEV]
- **Jira:** EDM-3895
- **Epic:** EDM-3885 — Restore Command Enhancement
- **Feature:** EDM-3213 — Backup and Restore

### User Story

**As a** FlightCtl administrator,
**I want to** invoke `flightctl-restore <archive-path>` to restore from a backup archive,
**So that** I can restore FlightCtl state after a disaster.

### Acceptance Criteria

1. `flightctl-restore <archive-path>` accepts archive path as first positional argument
2. Restore command logs archive path when provided
3. Restore command extracts archive to temporary directory
4. Restore command reads `metadata.json` from extracted archive
5. Restore command validates deployment type matches current environment
6. Restore fails with clear error if deployment type mismatch
7. Restore fails with clear error if archive path does not exist or is not readable
8. Temporary extraction directory cleaned up on success or failure
9. Unit tests cover argument parsing, extraction, metadata validation

### Implementation Guidance

Modify `cmd/flightctl-restore/main.go` to accept the archive path as a
**required** positional argument (no backwards compatibility — see user note).
Create `internal/restore/archive.go` with archive extraction and metadata
validation functions. Update docs to reflect the new required argument.

### Testing Approach

**Unit tests:**
- Test argument parsing (0 args → clear error, 1 arg → OK, >1 args → error)
- Test archive path validation (file exists, file readable, directory instead of file)
- Test extraction (tar.gz → temp dir with metadata.json)
- Test metadata validation (deployment type match, mismatch → error)
- Test temp dir cleanup on success and failure

### Dependencies

No story dependencies.

## Design Context

### Relevant Design Sections

From `design.md` §4.1 (Architecture — Restore command workflow):

> **Restore command** (enhanced `flightctl-restore`):
> - Validates archive integrity (SHA256 checksum)
> - Extracts archive to temporary directory
> - Checks for `db/dump.sql` in archive
> - Restores PKI materials and service config
> - Runs existing device preparation logic
> - Cleanup: removes temporary directory

This story implements the **archive extraction and metadata validation** phase only
(steps 1-5 in the conceptual restore workflow). The DB restore, PKI restore, and
config restore are implemented in later stories. The device preparation step
(`restore.PrepareDevices`) will be called at the end of the full workflow.

The `BackupMetadata` struct in `internal/backup/backup.go` is the canonical metadata
format. The restore package must read and validate it.

**User clarification:** No backwards compatibility with the old argument-free
`flightctl-restore` behavior. The archive path argument becomes effectively required.
Documentation will be updated to reflect this.

### PRD Requirements Covered

FR-8 (restore from backup archive), NFR-2 (build on existing patterns).

## Codebase Context

### Affected Components

#### cmd/flightctl-restore
- **Location:** `cmd/flightctl-restore/main.go`
- **Purpose:** CLI entry point for restore operation
- **Current patterns:** Cobra command, `SilenceUsage: true`, version subcommand, `runRestore(ctx)` func
- **What changes:** Add positional archive path arg, pass it to archive extraction before calling `runRestore`

#### internal/restore (new: archive.go)
- **Location:** `internal/restore/`
- **Purpose:** Post-restoration logic (existing: `prepare.go`, `store.go`)
- **Current patterns:** Package-level functions, no exported types beyond `RestoreStore`
- **What changes:** New `archive.go` with extraction and metadata validation functions

#### internal/backup (read-only reference)
- **Location:** `internal/backup/backup.go`, `internal/backup/deployer.go`
- **Purpose:** Provides `BackupMetadata` struct and `DeploymentType` constants to reuse in restore
- **What changes:** None — restore imports and reuses these types

### Relevant Types and Interfaces

```go
// From internal/backup/backup.go
type BackupMetadata struct {
    Timestamp        time.Time      `json:"timestamp"`
    Version          string         `json:"version"`
    DeploymentType   DeploymentType `json:"deploymentType"`
    DatabaseIncluded bool           `json:"databaseIncluded"`
}

// From internal/backup/deployer.go
type DeploymentType string
const (
    DeploymentTypePodman     DeploymentType = "podman"
    DeploymentTypeKubernetes DeploymentType = "kubernetes"
    DeploymentTypeUnknown    DeploymentType = "unknown"
)

// DetectDeployment — used in backup to get current deployer type:
func DetectDeployment(cfg *config.Config, log logrus.FieldLogger, basePath string) (Deployer, error)
```

The restore archive extraction must:
1. Open the `.tar.gz` file
2. Extract to `os.MkdirTemp`
3. Read and unmarshal `metadata.json` from the extracted directory
4. Detect current deployment type (reuse `backup.DetectDeployment` or replicate the logic)
5. Compare `metadata.DeploymentType` against current environment
6. Return error on mismatch, return extracted dir path on success

### Relevant APIs

No API changes. CLI-only.

## Repository Topology

- **Origin:** asafbennatan/flightctl (GitHub)
- **Type:** Direct clone (not a fork per `gh repo view`)

## Validation Profile

### Commit Format
- **Pattern:** `EDM-NNNN: Short description of the change`
- **Discovered from:** CONTRIBUTING.md and git log

### Pre-PR Checks (ordered)
1. `make tidy` — tidy go.mod files
2. `make lint` — golangci-lint (do not invoke directly; uses make)
3. `make unit-test` — full unit test suite (prefer running changed packages first)

### PR Conventions
- **Title format:** `EDM-3895: Description`
- **PR template:** None (no `.github/PULL_REQUEST_TEMPLATE.md`)
- **Description guidance:** Keep changes focused; CI must pass

### Coverage Tooling
- **Command:** `go test -coverprofile=coverage.out ./internal/restore/... ./cmd/flightctl-restore/...`
- **Minimum new-code coverage:** 90% (project default)

### Discovered from
- `AGENTS.md`, `CONTRIBUTING.md`, `Makefile`, `cmd/flightctl-restore/main.go`,
  `internal/restore/prepare.go`, `internal/restore/store.go`,
  `internal/backup/backup.go`, `internal/backup/deployer.go`,
  `internal/backup/backup_test.go`, git log

## Open Questions

1. Should deployment type detection in restore use `backup.DetectDeployment` directly
   (importing from `internal/backup`), or should `internal/restore` implement its own
   independent detection to avoid a cross-package dependency between `restore` and `backup`?
   (The planner should examine import graphs and decide.)
2. Should the archive path be a required positional arg (error if missing) or an optional
   one where missing triggers a clear "archive path required" error? (Either works; the
   distinction is in Cobra's `Args` validator vs runtime check.)
