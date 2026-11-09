---
name: screenshot-inspection
version: 0.1.0
---
# Recipe: Screenshot Inspection

Inspect published screenshots referenced in a UX handoff document.
Used by `ui-design` `/ingest` to verify image identity and visually
observe the actual design assets.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| HANDOFF_DIR | Yes | Absolute path to the directory containing the published handoff |
| MANIFEST_PATH | Yes | Absolute path to the published `screenshot-manifest.json` |
| HANDOFF_FILE | Yes | Path to the handoff file — required for Screenshot Index ID accounting |

## Procedure

### 1. Read manifest

Read the manifest at `{MANIFEST_PATH}`. It contains per-image `sha256`,
`context_revision`, `prototype_iteration`, `caption`, and `alt_text`.
If the manifest is missing, warn the user and record `manifest: unavailable`
per image.

### 2. Resolve image references

Determine the reference type from the handoff embeds:

**Local references** (`screenshots/SS-N-desc.png` -- `lfs` or `git`
mode): **Path containment.** Before opening any local file, reject
paths containing `..` components or absolute paths. Resolve each
candidate against `{HANDOFF_DIR}` and verify the resolved path remains
inside `{HANDOFF_DIR}`. If the path is a symlink, verify its target is
also inside `{HANDOFF_DIR}`. Stop and report any reference that
escapes. Then locate the image file relative to `{HANDOFF_DIR}`. If the file
is a Git LFS pointer stub (starts with `version https://git-lfs`),
attempt `git lfs smudge` or record `inspection: lfs-unresolved`.

**External references** (`https://...` URLs -- `external` mode):
Retrieve image bytes using the runtime's binary download capability
(save to a temporary file). If download fails, record
`inspection: fetch-failed`.

### 3. Verify identity and inspect

For each resolved image (local file or fetched external):

1. **Verify identity.** If the manifest provides `sha256`, compute the
   SHA-256 of the actual image bytes and compare. Record
   `identity: verified`, `identity: mismatched`, or `identity: unverified`
   (when manifest is unavailable).

2. **Open and visually inspect** using the runtime's image reading
   capability (the `Read` tool on the file path). Reading markdown,
   metadata, captions, or alt text alone is **not** image inspection --
   observe the actual rendered layout, visual hierarchy, spacing, color,
   component arrangement, and state presentation.

   If identity is `mismatched`, still record observations but flag the
   image as stale/unverified.

3. **Record** per image using this schema:

   | Field | Value |
   |-------|-------|
   | `id` | Screenshot ID (`SS-N`) |
   | `status` | `inspected` / `unavailable` / `lfs-unresolved` / `fetch-failed` / `inspection-not-supported` |
   | `identity` | `verified` / `mismatched` / `unverified` |
   | `ref` | Published reference (local path or external URL) |
   | `expected_sha` | SHA-256 from manifest (or `—` if unavailable) |
   | `observed_sha` | SHA-256 of actual bytes (or `—` if not resolved) |
   | `observation` | Brief description of actual visual content |
   | `spec_match` | `Yes` / `No` — consistency with written description |
   | `notes` | Visual details not in spec, or failure reason |

   When the user explicitly accepts a `mismatched` or `unverified` image,
   record that decision so downstream phases can cite it as
   `[Screenshot: SS-N — accepted-unverified]`. Do not silently accept
   missing manifests or identity mismatches.

4. **If unresolvable:** Record the ID and per-image status per the
   schema above. Report which images could not be inspected. Do **not**
   fabricate observations from captions or alt text. Ask the user
   whether to proceed with partial/text-only context or wait for full
   image access.

5. **Check revision binding (separate from identity).** Byte-identity
   verification (step 3.1) and revision-binding validity are
   independent checks — a verified SHA must not erase a binding
   mismatch.

   Read the manifest's top-level `context_revision` and
   `prototype_iteration` (the actual published fields). Read the
   handoff's metadata header for its declared revision/iteration. For
   each image, record:

   | Binding | Expected (handoff header) | Actual (manifest) | Match |
   |---------|--------------------------|-------------------|-------|
   | `context_revision` | {from header} | {from manifest} | `matched` / `mismatched` / `unknown` |
   | `prototype_iteration` | {from header} | {from manifest} | `matched` / `mismatched` / `unknown` |

   Record binding status in the Notes column of the per-image schema
   (keeping 9 columns) with the actual expected/actual values and
   match status. Default missing fields to `unknown` — never treat an
   absent binding as vacuously `matched`.

   When any binding is `mismatched` or `unknown`, prompt the user
   **per image** to accept or reject and persist the decision in
   Notes (e.g., `binding: mismatched, ctx_rev expected=r3 actual=r2,
   decision=accepted`). A verified SHA cannot clear a binding
   mismatch. See §5 Eligibility for citation rules.

### 4. Account for every declared index ID

Read `{HANDOFF_FILE}`'s **Screenshot Index** section and collect all
declared `SS-N` IDs. Match each declared ID to an actual image embed
(`![...](...)` in the handoff body) by **both** the ID and its declared
ref path. Consume each embed at most once — a shared ref path cannot
satisfy two distinct IDs from one embed.

- **IDs with a matching embed:** these are the images processed in
  steps 2–3 above.
- **IDs without an embed or whose embed was already consumed:** record
  as a 9-column row with `status: unavailable`, `identity: —`,
  `observation: —`, `spec_match: —`, and
  `notes: "declared in index but no matching embed found"`. Include
  in the output and aggregate totals.

Run this accounting **before** computing the final aggregate status or
eligibility. The total is the count of declared IDs, not the count of
discovered embeds.

Report the full accounting:
- **Total declared:** count of IDs in the Screenshot Index
- **Embeds found:** count with matching image embeds
- **Missing embeds:** count without embeds (list the IDs)

If any IDs have missing embeds, warn the user and prompt: repair the
handoff to add the missing embeds, or explicitly authorize partial
continuation (text-only for those IDs). Never silently omit a declared
ID or claim all images were inspected when embeds are missing.

### 5. Eligibility and citation rules

Callers (e.g. `/plan`) read this section for citation policy; they
must not rerun image inspection. Evaluate each image in rule order:

**Rule 1 — Inspection gate.** `status` must be `inspected`. Any
other status (`unavailable`, `lfs-unresolved`, `fetch-failed`,
`inspection-not-supported`) → **ineligible**. Do not cite.

**Rule 2 — Identity.** `identity` must be `verified` (no action
needed), or `mismatched`/`unverified` with explicit per-image user
acceptance. Any other value, or a rejected/unprompted/deferred
decision → **ineligible**.

**Rule 3 — Bindings.** Each binding (`context_revision`,
`prototype_iteration`) that is `mismatched` or `unknown` requires its
own explicit acceptance, independent of identity. Any rejected,
unprompted, or deferred binding → **ineligible**.

**Outcome:**

| Result | When | Citation |
|--------|------|----------|
| verified | inspected + identity `verified` + all bindings `matched` | `[Screenshot: SS-N]` |
| accepted-unverified | inspected + every applicable identity/binding exception explicitly accepted | `[Screenshot: SS-N — accepted-unverified]` |
| ineligible | any rule blocks use | Do not cite |

Rejected, deferred, or unavailable evidence must not be used for
planning decisions — not merely given a different citation tag.
Accepted-unverified evidence stays usable but always carries the
qualified label.
