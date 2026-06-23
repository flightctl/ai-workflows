---
name: simplicity-ladder
version: 0.1.0
---
# Recipe: Simplicity Ladder

A quick decision checklist for choosing the simplest viable implementation.
Referenced by code-producing workflows before writing new code.

## The Ladder

Stop at the first rung that holds:

1. **Does this need to exist?** If the requirement is already met by
   existing code, or the feature is speculative — stop. YAGNI.
2. **Stdlib does it?** Use the language's standard library. Don't wrap it.
3. **Native platform feature?** Use it — OS API, runtime built-in,
   framework primitive, HTML/CSS over JS.
4. **Already-installed dependency?** Check existing deps before adding new
   ones. Never add a dependency for what a few lines can do.
5. **One-liner?** If the solution fits in one clear line or expression,
   write the one-liner. Don't build infrastructure around it.
6. **Minimum code that works.** Write the smallest correct implementation.
   No speculative abstractions, no premature generalization.

The ladder is a reflex, not a research project. Two rungs work — take the
higher one and move on.

## When NOT to Simplify

Do not simplify past correctness in these areas:

- **Trust boundaries** — input validation, authentication, authorization
- **Data-loss paths** — persistence, backup, transaction handling
- **Security** — cryptography, secret management, access control
- **Accessibility** — a11y requirements are not optional complexity
- **Explicitly requested features** — if the story or ticket asks for it,
  build it

## The `ceiling:` Comment Convention

When the ladder leads to a simpler approach that has a known limit,
optionally leave a `ceiling:` comment at the decision point:

```text
// ceiling: >5 routes with middleware → consider a router
```

The ceiling names the condition under which the simple choice stops
being adequate. It tells future maintainers when to revisit, not how
to refactor. Only add one when the limit is non-obvious — most simple
choices don't need annotation.
