---
name: ingest
description: Fetch and compact Feature data, then record only sizing-relevant context.
---

# Ingest Sizing Context

Use Python for deterministic Jira retrieval and payload compaction. Use AI only
to summarize requirements, connect them to the codebase, and identify uncertainty.

## Rules

- Jira reads only. Never create, update, transition, comment, or attach files.
- Capture evidence; do not assign sizes in this phase.
- Follow lateral links one level only. Do not fetch child issues or links of links.
- Generalize personal and customer-specific details in generated artifacts, as
  required by `../../_shared/content-rules.md`.
- In batch mode, identify shared code evidence once and reuse it across Features.
  Start with a few relevant files per Feature; expand only when needed to answer
  sizing questions.

## Process

1. Accept a Jira issue key/URL or `release:{project}:{version}`. For a URL,
   extract the key from `/browse/`. For a release, derive its artifact context
   before checking for existing artifacts: lowercase the version, replace each
   run of characters outside `a`–`z` and `0`–`9` with `-`, trim leading and
   trailing hyphens, and use `release` if the result is empty (for example,
   `1.5.0` becomes `1-5-0`). The helper's JSON `context` field confirms this
   value after the Jira fetch.
2. If `.artifacts/sizing/{context}/01-context.json` already exists and an
   assessment exists, explain that re-ingest will invalidate the assessment
   and wait for confirmation before fetching again. Do not remove or overwrite
   existing artifacts before replacement context has been fetched and rendered
   successfully.
3. Resolve the installed helper and capture its compact JSON output:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/prepare_context.py" single "<ISSUE-KEY>"
   python3 "${HOME}/.ai-workflows/sizing/scripts/prepare_context.py" release "<PROJECT>" "<VERSION>"
   ```

   Replace placeholders with the supplied values and run only the matching
   command. The helper uses the Jira CLI or the shared
   `../../_shared/scripts/fetch-issue.py` REST helper (directly if the CLI is
   unavailable, or as fallback when REST credentials are configured). It omits
   unused fields, comment authors, and previous sizing comments; keeps at most
   three recent substantive comments per Feature; and emits one compact JSON
   packet with an approximate payload size on stderr. Stop on errors. If the
   batch may have reached the result cap, raise `--max-results` and fetch again.
4. Check issue types. If a single issue is not a Feature, ask whether to
   continue. In batch mode, report and stop if any returned issue is not a
   Feature or if the query returns no results.
5. Explore only code relevant to the requested scope. Search the codebase for
   candidate components and inspect targeted implementation/test files. In a
   batch, do not reread shared files for every Feature. Record paths and short
   evidence; do not paste source files into the artifact.
6. Create a staging directory inside the context artifact directory, then write
   compact, sanitized JSON to its `01-context.json`. Keep the staging directory
   on the same filesystem as the final artifacts so the renderer can promote
   the files safely:

   ```bash
   mkdir -p ".artifacts/sizing/{context}" &&
     mktemp -d ".artifacts/sizing/{context}/.ingest-XXXXXX"
   ```

   Record mktemp's printed path and use it literally for file writing,
   rendering, retries, and cleanup; shell variables do not persist between
   commands.

   Use this shape for the staged JSON:

   ```json
   {
     "context": "EDM-2324",
     "mode": "single",
     "features": [{
       "key": "EDM-2324",
       "title": "Jira summary",
       "status": "Open",
       "priority": "Major",
       "fix_versions": ["1.3.0"],
       "current_size": null,
       "description_summary": "Requirements and acceptance criteria that affect scope.",
       "comments_summary": "Recent scope updates and unresolved questions, if any.",
       "components": [{"name": "api", "paths": ["src/api/handler.py"]}],
       "integrations": [],
       "data_model": "None identified",
       "testing_surface": "Existing API tests cover the relevant path.",
       "novelty": "Extending existing patterns",
       "linked_issues": [{
         "key": "EDM-2300",
         "relationship": "blocks",
         "summary": "Linked issue summary",
         "status": "In Progress",
         "note": "Potential sizing dependency"
       }],
       "confidence": "medium",
       "concerns": [],
       "evidence": ["src/api/handler.py: existing request flow"]
     }]
   }
   ```

   For batch mode set `mode` to `batch`; include `project` and `fix_version`.
   Preserve every Feature key. Each linked issue requires non-empty `key`,
   `relationship`, and `summary`; `status` and `note` are optional strings. The
   compact Jira packet uses `Unknown` when Jira omits a relationship or summary;
   use an empty list when there are no linked issues.
   Copy metadata from the compact Jira packet, but summarize descriptions and
   relevant comment details in `description_summary` and `comments_summary`;
   never copy them verbatim.
7. Render and validate the machine-readable context:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/render_context.py" \
     "<recorded-staging-path>/01-context.json" \
     --commit-to ".artifacts/sizing/{context}"
   ```

   The helper validates the staged JSON, renders staged `01-context.md`, then
   promotes both context files together. Only after both are installed does it
   invalidate stale `02-decisions.json`, `02-assessment.json`,
   `02-assessment.md`, and `03-apply-actions.json`. Promotion rolls back the
   previous artifacts if any replacement fails. Do not refetch Jira to repair
   a schema error.

   If the renderer reports a validation error for model-authored JSON, keep the
   recorded staging directory intact. Correct only the named field when its
   value is derivable from the captured Jira packet and existing evidence,
   then rerun the renderer with the same recorded path. Do not invent missing
   data or impose a fixed retry count.

   If the value is unavailable or the same validation error persists, remove
   only the recorded staging directory, leave existing artifacts unchanged,
   stop, and report the exact error under the dispatcher's retry or escalation
   policy. For any other helper error, remove only the recorded staging
   directory, stop, and report the exact error under that policy. If the error
   says rollback was incomplete, preserve the named recovery directory; in that
   case, do not assume existing artifacts are unchanged.

   Use the compact result summary to report Feature count, existing sizes,
   explored components, and low-confidence concerns. Do not reopen the
   rendered Markdown for the report. Remove the now-empty recorded staging
   directory.

## Output

- `.artifacts/sizing/{context}/01-context.json` — compact source for `/assess`
- `.artifacts/sizing/{context}/01-context.md` — human-readable rendered context

After reporting ingest results, return to the dispatcher for completion
guidance. Do not start `/assess` automatically.
