---
name: apply
description: Preview selected sizing actions and write approved sizes to Jira.
---

# Apply Sizing

Use `.artifacts/sizing/{context}/02-assessment.json` as the source of truth.
Do not read `02-assessment.md`; it is generated from the JSON artifact.

## Process

1. If the finalized JSON is missing, recommend `/assess` and stop.
2. Render the dry-run preview:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/apply_plan.py" preview "{context}"
   ```

   Show the preview as a selection summary. XXL Features are excluded and
   must be split. Ask which committable Features to include, whether any sizes
   should be overridden, or whether to cancel. If the user says "approve"
   without specifying a subset, select all committable Features for payload
   review; this is not authorization to write to Jira.
3. Prepare the Jira action payload from the selection. Before the first
   `actions` command that changes or clears a size override, capture the
   existing override map and keep it unchanged through payload revisions until
   the user approves or cancels:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/apply_plan.py" show-overrides "{context}"
   ```

   For example:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/apply_plan.py" actions "{context}" \
     --select-key EDM-2324 --override EDM-2324=M \
     --output ".artifacts/sizing/{context}/03-apply-actions.json"
   ```

   Use `--all` when the user selected every committable Feature. Map preview
   row numbers to issue keys before passing `--select-key`. Never include
   XXL or apply an override to XXL. Use `--clear-override ISSUE-KEY` (repeat as
   needed) when restoring an original recommendation that has a stored
   apply-time override. These options select payload actions; they do not
   authorize Jira writes. The helper validates changes, updates
   `02-decisions.json`, `02-assessment.json`, and `02-assessment.md` when an
   override is added or cleared, invalidates any older prepared payload, and
   builds Jira wiki comments deterministically. Continue only if this command
   completes successfully. If it fails or is unavailable, stop this attempt;
   do not proceed to step 4 or read or use an existing
   `03-apply-actions.json`.
4. Use the action helper's result to check whether it prepared any actions. If
   it prepared none, report that no committable Features are available and go
   to step 5 without requesting approval or calling Jira. Refer to the
   assessment to identify any XXL Features; do not infer their sizes from an
   empty payload.

   If no Jira write integration is available, do not read the payload, request
   write approval, or use another channel to write. Report that Jira is
   unchanged, give the prepared payload path, and go to step 5. Otherwise, read
   `03-apply-actions.json`, show every prepared action's Feature key, size, and
   full comment text, and wait for explicit approval of this exact payload
   before writing to Jira. If the user requests changes, regenerate the
   payload and show it again.

   **If the user explicitly approves this payload:** for each approved action:

   ```text
   jira_update_issue(
     issue_key: action.key,
     fields: {"customfield_10795": {"value": action.size}}
   )
   jira_add_comment(issue_key: action.key, comment: action.comment)
   ```

   The action helper does not contact Jira. If a size update fails, do not
   attempt its comment; stop before the remaining actions and go to step 5 with
   updated, failed, and unattempted Features listed. If only a comment fails,
   report the comment failure and continue with the remaining approved
   Features.

   **If the user cancels:** do not write to Jira. If this attempt changed or
   cleared apply-time overrides, restore each affected key to its pre-attempt
   state so unapproved choices do not remain in the assessment artifacts:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/apply_plan.py" restore-overrides \
     "{context}" --key EDM-2324 --override EDM-2300=S
   ```

   Use `--override ISSUE-KEY=SIZE` for each affected key that had a prior value
   in the saved map. Use `--key ISSUE-KEY` only when it had no prior value.
   This also removes any prepared action payload. If restoration fails, report
   the exact error and do not assume the artifacts were restored. Then go to
   step 5; do not write to Jira.
5. Report updated, partially updated, skipped, failed, and unattempted
   Features with direct Jira links. If no write integration was available,
   include the prepared payload path. Then return to the dispatcher for
   completion guidance. Do not run another phase automatically.

## Safety

- Never write before the user explicitly approves the displayed action
  payload, including its full Jira comment text.
- A user size override is written back to the JSON and rendered assessment
  before Jira updates. If the payload is canceled, restore changed override
  keys to their pre-attempt values before returning to the dispatcher.
- If a Feature is XXL, do not update Jira. Point to its split recommendations.
