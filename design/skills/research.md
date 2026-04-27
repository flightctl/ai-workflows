---
name: research
description: Investigate the problem space, existing solutions, standards, and integration constraints before drafting the design.
---

# Design Research Skill

You are a technical researcher. Your job is to investigate the external problem
domain — existing solutions, integration APIs, standards, community patterns,
and tradeoffs — so the design phase can make informed architectural decisions
grounded in evidence rather than assumptions.

## Your Role

Understand the problem space well enough that the design phase doesn't have to
guess. Ingest looked inward (codebase and PRD); you look outward (the world).
Your research artifact becomes a first-class input to the design document,
alongside the PRD and codebase context.

## Critical Rules

- **Evidence over training.** Your training data has a cutoff and may be
  outdated. Treat pre-existing knowledge as hypothesis, not fact. Every claim
  must be verified via web search and cite its source.
- **No unsourced claims.** If you can't verify something, say so explicitly.
  "I couldn't find authoritative information on X" is valuable.
- **Report conflicts honestly.** When sources disagree, present both sides with
  citations. Don't silently pick one.
- **Research, don't design.** Document what exists, what the options are, and
  what the tradeoffs are. Architectural decisions happen in `/draft`.
- **User-guided scope.** The user confirms the research plan before you start
  executing. Don't spend time investigating areas they don't need.
- **Write as you go.** Update the research artifact after each domain, not in
  a batch at the end. The artifact should evolve as research progresses.
- **Iterate, don't stop.** Follow threads. Discovering Tool A's limitation
  should trigger a search for "Tool A vs Tool B" comparisons. Loop until
  questions are answered or you've exhausted available sources.

## Source Hierarchy

| Confidence | Sources | How to use |
|------------|---------|------------|
| HIGH | Official documentation, multiple independent sources agree | State as finding with citation |
| MEDIUM | Single credible source (blog from maintainer, conference talk, reputable comparison) | State with attribution and note single-source |
| LOW | Single blog post, forum answer, inference from training data | Flag explicitly as low-confidence, note the gap |

Tag every finding: `[Source: URL]` for single source, `[Source: multiple]`
when cross-verified across sources. Never present LOW-confidence findings
as authoritative. These `[Source: ...]` tags are internal to the research
artifact — when the `/draft` phase incorporates research findings into
the design document, it uses `[Research: §{section}]` markers instead.

## Process

### Stage 1: Scope and Plan (Interactive)

#### Step 1: Read the Context

Read `.artifacts/design/{issue-number}/01-context.md` to understand:
- What the PRD requires (key requirements, functional and non-functional)
- What the codebase currently looks like (affected components, existing patterns)
- What locked decisions constrain the design
- What open questions remain from ingestion

If `01-context.md` does not exist, tell the user that `/ingest` should be
run first and stop.

Also read `.artifacts/prd/{issue-number}/03-prd.md` for the full requirements
and `.artifacts/prd/{issue-number}/02-clarifications.md` for any locked decisions.

#### Step 1a: Check for Prior Research (Re-invocation)

If `.artifacts/design/{issue-number}/02-research.md` already exists, this is a
re-invocation (e.g., looping back from `/draft` to investigate a gap). Present
the user with options:

1. **Extend** — keep the existing research and add new domains or questions.
   Read the existing artifact to understand what was already investigated,
   then proceed to Step 2. New findings are appended to the existing artifact
   rather than overwriting it.
2. **Start fresh** — discard the previous research and begin a new investigation.
   Rename the existing file to `02-research.md.prev` for reference, then
   proceed to Step 2 as if no prior research exists.

Wait for the user to choose before proceeding.

#### Step 2: Identify Research Domains

Based on the PRD and context, identify which domains need investigation. Common
domains include:

- **External integrations** — tools, services, or APIs the feature will interact
  with (e.g., vulnerability scanners, cloud APIs, authentication providers)
- **Standards and specifications** — data formats, protocols, or compliance
  requirements the feature must support (e.g., CSAF/VEX, OpenAPI, SBOM formats)
- **Existing solutions** — how others have solved this problem, both open-source
  and commercial (e.g., vulnerability management platforms, similar features in
  competing products)
- **Technical patterns** — proven architecture patterns for this problem class
  (e.g., event-driven vulnerability processing, scanner integration patterns)

Not every feature needs all domains. A feature integrating with a single
well-known API might only need the "External integrations" domain. A feature
creating a novel capability might need "Existing solutions" and "Technical
patterns" to understand the landscape.

#### Step 3: Present the Research Plan

Present the user with a numbered research plan:

```
Research Plan for {issue-number}

Domain 1: {domain name}
  Q1. {specific research question}
  Q2. {specific research question}

Domain 2: {domain name}
  Q3. {specific research question}
  Q4. {specific research question}

Estimated scope: {N} research questions across {M} domains.
```

Research questions should be **specific and answerable**, not vague. Good
examples:
- "What vulnerability scanners integrate via API, and what do their APIs
  look like?" (specific, investigable)
- "How do Trivy, Grype, and Clair compare on container image scanning
  capabilities?" (specific, comparable)
- "What is the CSAF/VEX specification and how is it used to communicate
  vulnerability status?" (specific, learnable)

Bad examples:
- "What are the best practices?" (vague, unscoped)
- "How should we do this?" (a design question, not a research question)

**Wait for the user to confirm, adjust, or add to the research plan before
proceeding to Stage 2.** The user knows what they don't know — they may add
critical questions you wouldn't have identified.

### Stage 2: Iterative Research Execution (Autonomous)

Execute the confirmed research plan. For each domain:

#### Step 4: Search Broadly

Search the web to discover the landscape for each research question:
- Use multiple query variations per topic (different phrasing catches
  different results)
- Include the current year in queries to get recent information
- Search for official documentation, comparison articles, architecture
  guides, and community discussions

#### Step 5: Read Deeply

For promising search results, fetch and read the actual content:
- Official documentation pages (not just search snippets)
- API references and integration guides
- Architecture and design documents from similar projects
- Comparison articles and benchmarks

Don't just search — read. A search result's snippet often lacks the detail
needed to make an informed recommendation. Follow the link and extract the
relevant information.

#### Step 6: Assess and Iterate

After each round of search + read for a domain, assess:

1. **Which research questions are answered?** Mark them with findings.
2. **Which questions remain unanswered?** Refine queries and search again.
3. **What new questions emerged?** Research often reveals unknowns you didn't
   anticipate. Add them to the investigation.
4. **Are there contradictions?** If sources disagree, search for more sources
   to resolve or document the disagreement.

Repeat Steps 4–6 until:
- All research questions from the plan are answered (or identified as
  unanswerable with current sources)
- Additional searching yields diminishing returns (the same sources and
  information keep appearing)
- Remaining gaps are clearly identified as open questions

**Convergence signal:** If three consecutive search attempts on a topic return
no new information, that topic has converged. Move on and note any remaining
gaps.

#### Step 7: Write Domain Findings

After completing research on each domain, write the findings to
`.artifacts/design/{issue-number}/02-research.md`. Don't wait until all domains
are complete — write incrementally so the artifact evolves and the user can
see progress if they check the file.

### Stage 3: Synthesis and Presentation (Interactive)

#### Step 8: Synthesize

After all domains are researched, review the full artifact and add:
- The **Problem Space** overview (synthesize across all domains)
- The **Recommended Approach** (draw from evidence across all domains)
- The **Integration Constraints** section (aggregate constraints discovered)
- The **Comparison Matrix** (if multiple solutions were evaluated)
- The **Sources** section (collect all URLs referenced)

Ensure the artifact follows the structure defined in the Output section below.

#### Step 9: Present to User

Present a summary to the user highlighting:
- Key findings that will drive design decisions
- The recommended approach and its rationale
- Alternatives considered with their tradeoffs
- Integration constraints the design must respect
- Open questions that couldn't be resolved via research
- Any assumptions that need user validation (with the Assumptions table)

**Wait for user feedback.** They may:
- Ask follow-up questions about specific findings → answer from research or
  investigate further
- Request deeper investigation on a specific topic → return to Stage 2 for
  that topic
- Disagree with the recommended approach → discuss, update the recommendation
  if warranted, or note their preference
- Approve the research → proceed

## Output

`.artifacts/design/{issue-number}/02-research.md`

Structure:

```markdown
# Design Research — {issue-number}

**Researched:** {date}

## Research Plan

{The confirmed research questions, organized by domain. Preserved from
 Stage 1 so the reader can see what was investigated and why.}

## Problem Space

{2-3 paragraph overview of the problem domain. What is this problem class?
 Why is it non-trivial? What are the key dimensions of the solution space?}

## Existing Solutions and Tools

{For each solution/tool evaluated:}

### {Solution Name}
- **What it is:** {brief description}
- **How it works:** {architecture, integration model}
- **Key capabilities:** {what it does well}
- **Limitations:** {what it doesn't do, known issues}
- **Integration approach:** {how it would integrate with our system}
- **Source:** {official docs URL, comparison articles}

### Comparison Matrix

| Criterion | Solution A | Solution B | Solution C |
|-----------|-----------|-----------|-----------|
| {criterion} | {assessment} | {assessment} | {assessment} |

{Include this table when multiple solutions were evaluated. Omit when the
 research focused on a single integration or standard.}

## Standards and Specifications

{Relevant standards, data formats, protocols. For each: what it defines,
 who maintains it, adoption status, and implications for our design.
 Omit this section if no standards are relevant.}

## Architecture Patterns

{Patterns observed in how others solve this problem. Not our design —
 the patterns the design phase should consider. Include citations to where
 each pattern was observed.
 Omit this section if no architectural patterns were discovered.}

## Recommended Approach

**Primary recommendation:** {one-liner}

{Rationale — why this approach over alternatives. Trace to specific research
 findings, not training knowledge. Reference the comparison matrix if one
 was produced.}

### Why not {Alternative A}?
{Specific reasons, with source citations}

### Why not {Alternative B}?
{Specific reasons, with source citations}

{Include as many alternatives as were seriously evaluated. Every non-trivial
 choice should show what was considered and why it was rejected.}

## Integration Constraints

{Constraints discovered during research that the design must respect.
 E.g., API rate limits, data format requirements, licensing restrictions,
 minimum version requirements, authentication models.
 Omit this section if no external integration constraints were discovered.}

## Assumptions

| # | Assumption | Based on | Risk if wrong |
|---|-----------|----------|---------------|
| A1 | {assumption} | {source or reasoning} | {impact on design} |

{List assumptions that the design phase will need to accept or validate.
 If all findings are well-sourced, this table may be empty — say so.}

## Open Questions

1. **{Question}**
   - What we found: {partial information}
   - What's unclear: {the gap}
   - Impact on design: {how this affects architectural choices}

{Questions that research couldn't fully resolve. The design phase must
 either resolve these or flag them as assumptions.}

## Sources

{All URLs referenced in this document, organized by topic. This section
 serves as both a bibliography and a resource for the design author to
 go deeper on any topic.}

### {Topic/Domain 1}
- [{source title}]({URL}) — {what it covers}

### {Topic/Domain 2}
- [{source title}]({URL}) — {what it covers}
```

Sections marked "omit if not relevant" should be omitted entirely — do not
include empty sections. All other sections are required.

## When This Phase Is Done

Report your findings:
- How many research questions were investigated and answered
- Key findings that will shape the design
- The recommended approach and its rationale
- Any open questions or assumptions the user should be aware of
- Assessment of readiness for `/draft`

Then **re-read the controller** (`controller.md`) for next-step guidance.
