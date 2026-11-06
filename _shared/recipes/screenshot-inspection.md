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

## Procedure

### 1. Read manifest

Read the manifest at `{MANIFEST_PATH}`. It contains per-image `sha256`,
`context_revision`, `prototype_iteration`, `caption`, and `alt_text`.
If the manifest is missing, warn the user and record `manifest: unavailable`
per image.

### 2. Resolve image references

Determine the reference type from the handoff embeds:

**Local references** (`screenshots/SS-N-desc.png` -- `lfs` or `git`
mode): Locate the image file relative to `{HANDOFF_DIR}`. If the file
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

5. **Check revision binding.** Record the manifest's `context_revision`
   and `prototype_iteration`. If these differ from the handoff's
   metadata header, warn the user that screenshots may be from a
   different evaluation cycle.
