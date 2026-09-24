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
   assessment exists, explain that re-ingest will make it stale and wait for
   confirmation before fetching again.
3. Resolve the installed helper and capture its compact JSON output:

   ```bash
   SIZING_SCRIPT="${HOME}/.ai-workflows/sizing/scripts/prepare_context.py"
   python3 "$SIZING_SCRIPT" single "$ISSUE_KEY"
   python3 "$SIZING_SCRIPT" release "$PROJECT" "$VERSION"
   ```

   Run only the command for the supplied mode. The helper captures the
   configured Jira CLI's raw responses when the CLI is installed; otherwise
   it uses the shared `fetch-issue.py` REST helper, which requires `JIRA_URL`
   and `JIRA_TOKEN` (`JIRA_EMAIL` is optional). It omits unused Jira fields,
   comment authors, and previous sizing-assessment comments; it retains at most
   three recent substantive comments per Feature and emits one compact JSON
   packet. It reports an approximate payload size on stderr. Stop on errors; if
   the batch may have reached the result cap, raise `--max-results` and fetch
   again.
4. Check issue types. If a single issue is not a Feature, ask whether to
   continue. In batch mode, report and stop if any returned issue is not a
   Feature or if the query returns no results.
5. Explore only code relevant to the requested scope. Search the codebase for
   candidate components and inspect targeted implementation/test files. In a
   batch, do not reread shared files for every Feature. Record paths and short
   evidence; do not paste source files into the artifact.
6. Write compact, sanitized JSON to
   `.artifacts/sizing/{context}/01-context.json` using this shape:

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
       "linked_issues": [],
       "confidence": "medium",
       "concerns": [],
       "evidence": ["src/api/handler.py: existing request flow"]
     }]
   }
   ```

   For batch mode set `mode` to `batch`; include `project` and `fix_version`.
   Preserve every Feature key. Copy metadata from the compact Jira packet, but
   summarize descriptions and relevant comment details in `description_summary`
   and `comments_summary`; never copy them verbatim.
7. Render and validate the machine-readable context:

   ```bash
   python3 "${HOME}/.ai-workflows/sizing/scripts/render_context.py" \
     ".artifacts/sizing/{context}/01-context.json"
   ```

   The helper writes `01-context.md` and prints a short result summary. Use
   that summary to report Feature count, existing sizes, explored components,
   and low-confidence concerns. Do not reopen the rendered Markdown for the
   report.

## Output

- `.artifacts/sizing/{context}/01-context.json` — compact source for `/assess`
- `.artifacts/sizing/{context}/01-context.md` — human-readable rendered context

After reporting ingest results, return to the dispatcher for completion
guidance. Do not start `/assess` automatically.
