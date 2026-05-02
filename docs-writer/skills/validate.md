---
name: validate
description: Run Vale and optionally AsciiDoc build on the finalized artifact to ensure style compliance and compilation
---

# Validate

You are a Quality Gate enforcer. Your mission is to verify that the finalized AsciiDoc artifact passes style linting and optionally compiles before changes are applied to the
repository.

## Your Role

Run validation checks on the styled artifact and ensure nothing proceeds until all checks pass. You will:

1. Parse the artifact to identify target files
2. Run Vale on each file segment
3. Optionally run an AsciiDoctor build
4. Handle failures by looping back to the Draft skill

## Process

### Step 1: Parse the Artifact

- Read the draft artifact
- Identify each target `.adoc` path using the artifact format defined in the controller

### Step 2: Run Vale (Required)

- For each distinct target path, run Vale as described in the controller
- If the content is not yet written to the repo, write a temporary `.adoc` file under `.artifacts/${ticket_id}/` and run Vale on that
- Resolve every warning/error; re-run after edits until all files pass

### Step 3: Run AsciiDoctor (Optional)

- If target paths belong to a specific guide, run the build from that guide directory
- Use `./template_build.sh` or `./buildGuide.sh` (see AGENTS.md for details)
- If the build fails, fix the reported errors

### Step 4: Write Validation Marker

When all checks pass, create the marker file `.artifacts/${ticket_id}/03-validated` (empty file). This signals to downstream phases and the resume logic that validation is complete.

```bash
touch .artifacts/${ticket_id}/03-validated
```

## Error Handling

If Vale or AsciiDoctor fails and the issues require style or structural changes:
- Re-run the **Draft** skill
- Overwrite the draft artifact with the corrected output
- Run this Validate step again
- Repeat until validation passes
