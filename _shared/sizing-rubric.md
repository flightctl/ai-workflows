---
name: sizing-rubric
version: 0.1.0
---
# Sizing Rubric

Shared sizing definitions used by the sizing workflow (for Features) and the
design workflow (for Epics). This file is the single source of truth for how
the AI determines T-shirt sizes. Both workflows reference it to ensure
consistent sizing across the planning process.

## Cycle Structure

A release cycle is **10 weeks**:

| Phase | Duration | Purpose |
|-------|----------|---------|
| Development | 6 weeks | Feature implementation |
| QE | 3 weeks | Quality engineering, e2e testing, regression |
| Release | 1 week | Release preparation, deployment |

Features are sized to fit within one cycle. Epics are sized relative to the
development portion of the cycle. Stories are not sized — they are constrained
by definition (1 assignee, less than a week).

## Hierarchy

```text
Cycle (10 weeks: 6 dev + 3 QE + 1 release)
  └── Feature  [T-Shirt: XS/S/M/L/XL — always fits in one cycle. XXL = must split]
        └── Epic  [T-Shirt: XS/S/M/L/XL — maps to dev-weeks. XXL = must split]
              └── Story  [No size — 1 assignee, less than a week max]
```

## Size Definitions

These definitions apply to both Features and Epics. For Features, sizes are
relative to the full cycle. For Epics, sizes are relative to the development
phase (6 weeks).

| Size | Label | Duration | Meaning |
|------|-------|----------|---------|
| XS | Extra Small | Up to 2 days | Minimal scope, well-understood change |
| S | Small | Up to 1 week | Narrow scope, low risk, few components |
| M | Medium | ~1–2 weeks | Moderate scope, multiple can coexist in a cycle |
| L | Large | Up to ~3 weeks | Roughly half the dev phase, significant scope |
| XL | Extra Large | ~4–6 weeks | Most of a cycle, demands focus |
| XXL | Must Split | — | This must be scoped down before commitment |

## XXL Protocol

XXL is a **temporary flag**, not a committable size. It exists only to signal
that a Feature or Epic is too large and must be split before it can be
committed to a cycle.

When a Feature or Epic is assessed as XXL:

1. **Flag it immediately.** Do not proceed as if it will fit.
2. **Suggest split boundaries.** Split by user-value slice, not by technical
   layer. Each slice should deliver independent value.
3. **Re-assess each slice.** After splitting, each resulting Feature or Epic
   should be XL or smaller.
4. **Never commit XXL to a cycle.** If a Feature is XXL after assessment, it
   must be scoped down or split before it enters cycle planning.

## Sizing Heuristics

When assessing a Feature or Epic, evaluate these dimensions. Each dimension
contributes to the overall size. No single dimension determines the size —
use judgment to weigh them based on the specific context.

### Scope Breadth

How many distinct capabilities or outcomes does this deliver?

- **Low (XS–S):** Single capability, focused change
- **Medium (M):** 2–3 related capabilities
- **High (L–XL):** Multiple capabilities spanning different user workflows
- **Very High (XXL signal):** Broad scope touching many unrelated outcomes

### Component Surface

How many codebase components (packages, services, modules) are affected?

- **Low (XS–S):** 1–2 components, well-contained
- **Medium (M):** 3–5 components with clear boundaries
- **High (L–XL):** 5+ components, cross-cutting changes
- **Very High (XXL signal):** Most of the codebase is affected

### Integration Surface

How many APIs, external systems, or cross-team touch points are involved?

- **Low (XS–S):** No external integrations, internal-only
- **Medium (M):** 1–2 integration points with well-defined interfaces
- **High (L–XL):** Multiple integration points, some with uncertainty
- **Very High (XXL signal):** Heavy external coordination required

### Novelty

Is this extending existing patterns or building something new?

- **Low (XS–S):** Following established patterns exactly
- **Medium (M):** Extending existing patterns to new use cases
- **High (L–XL):** New patterns, new abstractions, new infrastructure
- **Very High (XXL signal):** Unproven approach, research needed

### Risk and Unknowns

How much uncertainty exists about the approach or outcome?

- **Low (XS–S):** Well-understood domain, clear path
- **Medium (M):** Some unknowns that can be resolved during design
- **High (L–XL):** Significant unknowns, unfamiliar domain, dependencies on external teams
- **Very High (XXL signal):** Fundamental unknowns that may invalidate the approach

### Testing Surface

How much new test infrastructure or coverage is needed?

- **Low (XS–S):** Existing test patterns apply directly
- **Medium (M):** New test cases but existing infrastructure
- **High (L–XL):** New test infrastructure, new e2e scenarios, complex setup
- **Very High (XXL signal):** Entirely new testing approach needed

## Team Effort Assessment

For each Feature, break down the effort by team. Each team gets its own
T-shirt size (using the same XS–XL scale) with a rationale explaining what
drives that team's effort.

### DEV (Development)

Driven by:
- Number of components to modify or create
- Integration surface — API changes, service interactions, data model changes
- Novelty — new patterns vs. extending existing ones
- Volume of production code changes

### QE (Quality Engineering)

Driven by:
- Number of e2e test scenarios needed
- New test infrastructure requirements (fixtures, environments, data setup)
- Risk surface — how much regression testing is needed
- Complexity of user-facing workflows to validate

### UX (User Experience)

Driven by:
- New user flows vs. adjustments to existing flows
- User research needs — does this require discovery or validation?
- Interaction complexity — new patterns, complex state management
- If no UX work is needed, size is "—" (not applicable)

### UI (User Interface)

Driven by:
- New components vs. composition of existing components
- Responsive and accessibility requirements
- Visual complexity — styling, animation, layout changes
- If no UI work is needed, size is "—" (not applicable)

### DOCS (Downstream Documentation)

Driven by:
- New customer-facing documentation pages vs. updates to existing pages
- Complexity of the feature from an end-user explanation perspective
- Number of procedures, concepts, or reference topics required
- If no downstream docs work is needed, size is "—" (not applicable)

Note: upstream (community/open-source) documentation is produced by developers
as part of DEV effort. DOCS covers only downstream, customer-facing documentation.

When a team has no involvement in a Feature, use "—" instead of a size.

## Impact vs. Effort Classification

After sizing determines the *effort* a Feature requires, classify each Feature
on a 2×2 impact-vs-effort matrix to support prioritization during cycle
planning.

### Impact Score

Assess impact by scoring four sub-dimensions independently. Each is rated
on a 1–5 scale. The composite impact score is the sum (range: 4–20).

#### Sub-dimensions

| Sub-dimension | 1 | 2 | 3 | 4 | 5 |
|---------------|---|---|---|---|---|
| **User Reach** | Internal-only or single user | Narrow segment, few workflows | Moderate user base, several workflows | Most users or a critical segment | All users, core workflow |
| **Pain Severity** | Cosmetic, no workaround needed | Minor friction, easy workaround | Noticeable pain, workaround exists but costs time | Significant pain, workaround is fragile or costly | Blocker — no viable workaround |
| **Strategic Alignment** | No connection to current goals | Tangential to a stated goal | Supports a goal indirectly | Directly advances a key goal | Critical to a top-priority initiative |
| **Dependency** | Nothing depends on this | Enables minor follow-on work | Unblocks one planned Feature | Unblocks multiple Features or a critical path | Gate for an entire release theme |

#### Impact Bands

| Band | Score Range | Meaning |
|------|------------|---------|
| High | 15–20 | Strong value signal across multiple sub-dimensions |
| Medium | 9–14 | Solid value but not uniformly strong |
| Low | 4–8 | Limited value — nice-to-have or narrow reach |

### Effort Score

Map the T-shirt effort size to a numeric value for ratio calculation:

| Size | Effort Score |
|------|-------------|
| XS | 1 |
| S | 2 |
| M | 4 |
| L | 7 |
| XL | 10 |

XXL Features are not scored — they must be split first.

### Priority Score

Priority Score = Impact Score / Effort Score (rounded to one decimal).

Higher is better. This score ranks Features within the same quadrant: a
Strategic Bet with priority 3.8 should be sequenced before one at 2.1.

### Effort-Impact Quadrant

Combine the effort size with the impact band to classify each Feature:

| Quadrant | Effort | Impact | Guidance |
|----------|--------|--------|----------|
| **Quick Win** | XS–S | High | Prioritize — high value for low cost |
| **Strategic Bet** | M–XL | High | Worth the investment — plan capacity carefully |
| **Low-Hanging Fruit** | XS–S | Low–Medium | Fill available capacity — easy wins when bandwidth allows |
| **Reconsider** | M–XL | Low | Challenge whether this belongs in the cycle at all |

Quadrant boundaries are guidelines, not hard rules. A Medium-effort /
Medium-impact Feature may be either a Strategic Bet or Low-Hanging Fruit
depending on context — use judgment and note the reasoning.

Within each quadrant, use the **priority score** to rank Features against
each other. The quadrant determines the category; the priority score
determines the sequence within that category.

## Calibration

This section captures after-the-fact observations from completed cycles.
These notes improve future sizing accuracy by grounding the heuristics in
real experience.

Format: one entry per observation, with the Feature key, original size,
actual effort, and what drove the difference.

```markdown
### {Feature-key}: {title}
- **Assessed:** {size}
- **Actual:** {size}
- **Delta driver:** {what caused the difference — e.g., "unexpected API
  complexity in integration with X," "UX scope expanded after user testing"}
```

<!-- Add calibration entries below as cycles complete -->
