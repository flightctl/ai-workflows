---
name: research
description: User research, data gathering, and synthesis into insights and design recommendations.
---

# Research — User Research

Conduct and synthesize user research to understand what users actually need.
The researcher drives data collection (interviews, surveys, observations);
the AI assists with organization, pattern identification, and synthesis.

## Prerequisites

Read `.artifacts/ux-design/{issue-key}/01-discovery.md` for the problem
framing and strategic decisions. If it doesn't exist, tell the researcher
that `/ingest` should run first and stop.

## Process

### Stage 1: Research Plan (Interactive)

#### Step 1: Propose Methodology

Based on the discovery brief's strategic decisions, propose a research plan:

- **Methods** — which research methods fit each question? (interviews,
  surveys, analytics review, support ticket analysis)
- **Participants** — who should be included? How many?
- **Data sources** — what existing data can the AI analyze directly?
  (support tickets, analytics, existing survey results, forum posts)

Present the plan to the researcher. Wait for confirmation before proceeding.
The researcher knows their constraints — adapt the plan to what's feasible.

#### Step 2: AI-Accessible Research

While the researcher conducts interviews or observations, the AI performs
desk research that doesn't require human participants:

- Analyze support tickets or bug reports related to the problem area
- Review forum posts, community discussions, or feedback channels
- Search for published usability studies on similar products
- Synthesize existing internal research documents

Cite all sources. Flag confidence levels (HIGH/MEDIUM/LOW).

### Stage 2: Data Organization (Collaborative)

#### Step 3: Intake Research Data

As the researcher gathers data (interview notes, survey responses,
observation notes), help organize it:

- Group findings by theme, not by participant
- Identify recurring patterns across data sources
- Flag contradictions or surprising findings
- Note frequency — how many participants mentioned each theme?

**Privacy:** Anonymize all participant data. Use role-based labels
("User P1", "Admin P2") instead of names.

#### Step 4: Identify Patterns

Across all data sources (researcher-gathered and AI desk research):

- What themes appear across multiple sources?
- What user needs are consistent vs. edge cases?
- Where do different user groups have conflicting needs?
- What workarounds are users employing today?

### Stage 3: Synthesis (Interactive)

#### Step 5: Generate Insights

Transform patterns into actionable insight statements:

**Format:** "{User group} needs {capability} because {reason}, but currently
{barrier}."

Each insight should:
- Be grounded in multiple data points
- Point toward a design direction
- Be specific enough to act on

#### Step 6: Design Recommendations

Based on insights, propose design recommendations:

- What should the solution prioritize?
- What user needs are critical vs. nice-to-have?
- What design constraints emerged from research?
- What risks should the prototype address first?

## Output

`.artifacts/ux-design/{issue-key}/02-research.md`

```markdown
# Research Findings — {issue-key}

**Date:** {date}
**Methods:** {list of methods used}
**Participants:** {count and roles, anonymized}

## Research Questions & Answers

### Q1: {strategic decision from discovery}
**Finding:** {what we learned}
**Evidence:** {data points, quotes, sources}
**Confidence:** {HIGH/MEDIUM/LOW}

### Q2: {strategic decision from discovery}
...

## Key Insights

1. **{Insight title}**
   {User group} needs {capability} because {reason}, but currently {barrier}.
   _Evidence: {data points}_

2. **{Insight title}**
   ...

## User Needs (Prioritized)

| Priority | Need | User Groups | Evidence Strength |
|----------|------|-------------|-------------------|
| Must-have | {need} | {groups} | {HIGH/MEDIUM/LOW} |
| Should-have | {need} | {groups} | {HIGH/MEDIUM/LOW} |
| Nice-to-have | {need} | {groups} | {HIGH/MEDIUM/LOW} |

## Persona Notes

{Where user groups interact differently with the feature, document
 persona-specific needs here. This feeds directly into the handoff's
 persona-specific views.}

| User Group | Distinct Needs | Distinct Behaviors |
|------------|---------------|-------------------|
| {group} | {what's different for them} | {how they use the feature differently} |

## Design Recommendations

1. {Recommendation with rationale traced to insights}
2. ...

## Risks & Open Questions

- {Risk or unresolved question with impact on design}

## Sources

- {Source with URL or description}
```

## When This Phase Is Done

Present the synthesized findings to the researcher:
"Here are the research findings and design recommendations. Do these
insights accurately reflect what you learned? Anything to add or correct
before we move to prototyping?"

Wait for confirmation. Then **re-read the controller** (`controller.md`)
for next-step guidance.
