---
name: assess
description: Apply the rubric and return compact Feature sizing judgments.
---

# Assess Sizing

If no context is known, inspect `.artifacts/sizing/` and ask which context to
assess. If no `01-context.json` exists, recommend `/ingest` and stop.

Read `.artifacts/sizing/{context}/01-context.json` and the Feature-relevant
sections of `../../_shared/sizing-rubric.md` (size definitions, XXL protocol,
heuristics, team effort, and impact classification). Do not read
`01-context.md`; it is a rendered view of the same data.

For each Feature, judge the overall size, all six heuristic levels, effort by
team, four impact scores, confidence, and any required split. In batch mode,
calibrate sizes together and note capacity or deferral concerns. The overall
size remains a judgment across the dimensions; do not calculate it from a
fixed formula. Give short, evidence-specific rationales. Explain disagreement
with a current Jira size.

Write only model judgments to `.artifacts/sizing/{context}/02-decisions.json`.
For a fresh assessment, omit any prior `user_overrides` map; apply-time
overrides belong to the previous assessment and are discarded. Use this shape:

```json
{
  "features": [{
    "key": "EDM-2324",
    "size": "M",
    "confidence": "medium",
    "dimensions": {
      "scope_breadth": {"level": "Medium", "rationale": "Two related user outcomes."},
      "component_surface": {"level": "Medium", "rationale": "API and controller paths."},
      "integration_surface": {"level": "Low", "rationale": "No external interface changes."},
      "novelty": {"level": "Low", "rationale": "Follows the existing request pattern."},
      "risk_unknowns": {"level": "Medium", "rationale": "Authorization edge cases need review."},
      "testing_surface": {"level": "Medium", "rationale": "Adds cases to existing API tests."}
    },
    "rationale": "The cross-component scope and authorization testing drive a Medium size.",
    "teams": {
      "DEV": {"size": "M", "rationale": "Changes span the API and controller."},
      "QE": {"size": "S", "rationale": "Adds focused authorization scenarios."},
      "UX": {"size": "—", "rationale": ""},
      "UI": {"size": "—", "rationale": ""},
      "DOCS": {"size": "—", "rationale": ""}
    },
    "impact": {
      "user_reach": {"score": 3, "rationale": "Several workflows use this API."},
      "pain_severity": {"score": 4, "rationale": "The failure blocks the affected workflow."},
      "strategic_alignment": {"score": 3, "rationale": "Supports the release goal indirectly."},
      "dependency": {"score": 2, "rationale": "No planned work depends on it."}
    },
    "value_driver": "Removes a workflow-blocking authorization failure.",
    "comparison_rationale": "Current size omits the additional controller and QE scope.",
    "quadrant": "Strategic Bet",
    "quadrant_rationale": "The controller work makes this a planned investment despite medium impact.",
    "split_suggestions": []
  }],
  "calibration_notes": "",
  "capacity_concerns": [],
  "defer_notes": {}
}
```

Use one decision for every context Feature, with the exact Jira key. Dimension
levels are `Low`, `Medium`, `High`, or `Very High`; team sizes are `XS`–`XL` or
`—`; impact scores are integers 1–5. Include `comparison_rationale` when the
assessment differs from an existing Jira size. For an overall size of `M`, `L`,
or `XL` with a combined impact score of 9–14 (Medium band), choose
`Strategic Bet` or `Low-Hanging Fruit` and provide `quadrant_rationale`. The
finalizer assigns quadrants for the other size/impact combinations. For XXL, give 2–3
user-value split suggestions, each sized XL or smaller. Add
`defer_notes` only for Features in `Reconsider`.

Finalize and render with Python:

```bash
python3 "${HOME}/.ai-workflows/sizing/scripts/finalize_assessment.py" "{context}"
```

The helper validates keys and allowed values, computes all score totals,
priority values, quadrants, chart points, comparisons, and batch summaries,
then writes `02-assessment.json` and `02-assessment.md`. Use its compact stdout
summary to present sizes, confidence, XXL items, Jira disagreements, and
capacity concerns. A successful finalization also removes any previously
prepared `03-apply-actions.json` payload. Do not reread the rendered Markdown.

If the finalizer reports a schema validation error in model-authored
`02-decisions.json`, correct only the named field when its value is derivable
from the rubric and existing `01-context.json`, then rerun the finalizer. Do not
invent missing information or impose a fixed retry count. If the value is not
derivable, the same error persists, or the failure is not a schema error in
model-authored data, stop and report the exact error under the dispatcher's
retry or escalation policy.

After presenting results, return to the dispatcher for completion guidance;
wait before `/apply`.
