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
3. Prepare the Jira action payload from the selection. For example:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/apply_plan.py" actions "{context}" \
     --approved-key EDM-2324 --override EDM-2324=M \
     --output ".artifacts/sizing/{context}/03-apply-actions.json"
   ```

   Use `--all` when the user selected every committable Feature. Map preview
   row numbers to issue keys before passing `--approved-key`. Never include
   XXL or apply an override to XXL. These options select payload actions; they
   do not authorize Jira writes. The helper validates overrides, updates
   `02-assessment.json` and `02-assessment.md` when needed, and builds Jira
   wiki comments deterministically.
4. Read `03-apply-actions.json` and show every prepared action's Feature key,
   size, and full comment text. Wait for explicit approval of this exact
   payload before writing to Jira. If the user requests changes, regenerate
   the payload and show it again. For each approved action:

   ```text
   jira_update_issue(
     issue_key: action.key,
     fields: {"customfield_10795": {"value": action.size}}
   )
   jira_add_comment(issue_key: action.key, comment: action.comment)
   ```

   The action helper does not contact Jira. If a size update fails, stop and
   report the error. If only the comment fails, report it and continue with the
   remaining approved Features.
5. Report updated and skipped Features with direct Jira links, then return to
   the dispatcher for completion guidance. Do not run another phase
   automatically.

## Safety

- Never write before the user explicitly approves the displayed action
  payload, including its full Jira comment text.
- A user size override is written back to the JSON and rendered assessment
  before Jira updates, keeping artifacts aligned with the approved action.
- If a Feature is XXL, do not update Jira. Point to its split recommendations.
