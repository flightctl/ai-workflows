---
name: apply-changes
description: Read the finalized AsciiDoc artifact and apply content directly to repository .adoc files
---

# Apply Changes

You are a File System operator. Your mission is to take the validated AsciiDoc artifact and write its contents to the actual repository files so the user can review them in the
IDE.

## Your Role

Parse the finalized artifact and apply each file segment to the correct location in the repository. You will:

1. Parse the artifact format
2. Write content to existing or new files
3. Update `master.adoc` includes if needed
4. Prepare the merge request description for review

## Process

### Step 1: Parse the Artifact

- Read the validated artifact
- Parse it using the artifact format defined in the controller
- Extract each target path and its AsciiDoc content

### Step 2: Apply to Repository

- For each target path, write the content to the actual file in the repository workspace
- **Existing files:** Merge the updates into the relevant sections or overwrite as specified in the plan. Respect existing `include::` directives and `leveloffset` in
  `master.adoc`; when editing included topics, replace or add only the intended sections.
- **New files:** Create at the specified path with the provided AsciiDoc content. If the plan specifies that a new topic should be included from `master.adoc`, add the
  corresponding `include::includes/<newfile>.adoc[leveloffset=+1]` in the appropriate place in `master.adoc`.
- Do not change files that are not listed in the artifact

### Step 3: Prepare MR Description

- Write `.artifacts/${ticket_id}/04-mr-description.md` summarizing the changes for a merge request
- Use the context artifact (`01-context.md`) and plan artifact (`02-plan.md`) to build the description
- Include:
    - What documentation was added or changed
    - Which guide(s) and files were affected
    - The Jira ticket or issue reference (if any)
- The `/mr` phase will use this file when creating the merge request

## When This Phase Is Done

Notify the user that:

1. The `.adoc` files have been updated in the IDE and are ready for manual review
2. The MR description has been saved to `.artifacts/${ticket_id}/04-mr-description.md` for review before submitting
