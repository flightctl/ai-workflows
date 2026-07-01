---
name: frontend-scan
description: Conditional sub-skill invoked by update.md when a frontend framework is detected. Identifies constraints and patterns for AGENTS.md enrichment.
---

# Frontend Scan

You are analyzing a frontend project to identify constraints and patterns that AI agents cannot infer from reading code alone. This skill is invoked conditionally by `update.md` when a frontend framework is detected in package dependencies.

## Critical Rules

- **Constraints are mandatory.** Always emit restricted imports, generated files, test framework absence, and i18n rules when detected. These are the highest-value findings.
- **Patterns are confidence-gated.** Only emit a pattern as canonical if it appears in 5+ distinct feature directories. When confidence is moderate (2–4 directories), place an HTML comment in the generated AGENTS.md (`<!-- ai-ready: candidate standard pattern: [description] — used in [N] directories -->`) for the user to confirm during review. When confidence is low (<2), skip it.
- **Verify everything.** Every file path and import in emitted content must exist in the current codebase.
- **Structure over prose.** Emit tables, short code examples (5–10 lines), and file path references — not paragraph descriptions.
- **Highest impact first.** Order output with restricted patterns at the top. Agents ignore instructions mid-file in long sessions ("lost in the middle"), so front-load the rules that prevent the most common mistakes.

## Process

### Step 1: Detect Constraints

These are high-value and mechanically detectable. Run all checks; skip any that find nothing.

#### Restricted imports

Parse the ESLint config (eslint.config.js, .eslintrc.js, .eslintrc.json, .eslintrc.yaml, .eslintrc.yml, .eslintrc) for `no-restricted-imports` rules. For each restricted import that includes a `message` field, emit a row in a "Restricted Patterns" table:

```markdown
| Restricted Import | Use Instead | Why |
|---|---|---|
| `library/Component` | `ProjectWrapper` from `src/components/...` | Project wrapper adds X |
```

If the ESLint config uses a flat config format (eslint.config.js with `export default`), parse the rules array. If it uses the legacy format (.eslintrc.*), parse the `rules` object. If the config cannot be statically parsed (e.g., TypeScript config, dynamic imports), note the config file location and skip this detection.

#### Wrapper components

Find files containing `eslint-disable-next-line no-restricted-imports` or `eslint-disable no-restricted-imports`. These files ARE the project's wrapper components — they import the restricted symbol to wrap it.

Cross-reference with the restricted imports table: for each wrapper file found, identify which restricted import it wraps and add or enrich the corresponding row in the Restricted Patterns table with the wrapper's file path.

#### Generated files

Check package.json `scripts` for codegen indicators — script names or commands containing `gen`, `generate`, `codegen`, `openapi`, `graphql-codegen`, `proto`, `swagger`, or `typegen`.

Also search for generated-file headers in source files:
- `/* generated */` or `/** generated */`
- `// Code generated` or `// This file is generated`
- `# DO NOT EDIT` or `# This file is auto-generated`
- `@generated` annotations

Emit a "Generated Files" list with the regeneration command for each:

```markdown
### Generated Files — Do Not Edit

| File / Pattern | Regenerate With |
|---|---|
| `src/api/types.ts` | `npm run generate-types` |
```

#### Test framework absence

Check for the ABSENCE of common unit test frameworks (jest, vitest, mocha, @testing-library/*) in both `dependencies` and `devDependencies`. Check separately for the PRESENCE of e2e frameworks (cypress, playwright, @playwright/test, nightwatch, testcafe).

If e2e frameworks are present but unit test frameworks are absent, this is a significant negative constraint. Emit it explicitly:

```markdown
### Testing Philosophy

This project tests exclusively through [framework] e2e tests. There are no unit tests.
Do not introduce jest, vitest, @testing-library, or other unit test frameworks.

Run e2e tests: `[command from package.json scripts]`
```

If both unit and e2e frameworks are present, note both with their run commands. If only unit tests are present, note the framework and run command.

#### i18n extraction rules

Check `devDependencies` for i18n tooling: i18next-parser, react-intl-cli, @formatjs/cli, babel-plugin-react-intl, vue-i18n-extract, @angular/localize, svelte-i18n.

If found, examine the tool's config file for:
- Key format convention (flat vs. nested, namespace rules)
- Extraction command (from package.json scripts)
- Whether components receive translated strings or translation keys as props

Emit a brief i18n section with the key format, extraction command, and the prop convention if detectable.

### Step 2: Detect Patterns

This step has two kinds of checks:

- **Dependency-presence checks** (design system, form library, state management, routing): If the package is in `dependencies`, emit it. No usage counting needed — presence in the manifest is sufficient signal.
- **Usage-frequency checks** (data fetching, URL-as-state, pagination, permissions): These detect conventions that could be one-offs or standards. Count usages across distinct feature directories (not total import count — a single file importing something 5 times does not make it a standard pattern). Only emit as a documented pattern if it meets the confidence threshold from the Critical Rules (5+ distinct feature directories).

#### Design system / component library

Check `dependencies` for UI component libraries:

- React ecosystem: `@patternfly/react-core`, `@mui/material`, `@chakra-ui/react`, `antd`, `@radix-ui/*`, `@headlessui/react`, `@mantine/core`
- Vue ecosystem: `vuetify`, `quasar`, `element-plus`, `naive-ui`, `primevue`, `@nuxt/ui`
- Angular ecosystem: `@angular/material`, `primeng`, `@ng-bootstrap/ng-bootstrap`, `@angular/cdk`
- Svelte ecosystem: `@skeletonlabs/skeleton`, `@smui/*`, `flowbite-svelte`
- Framework-agnostic: `@carbon/web-components`, `@shoelace-style/shoelace`

Emit library name and major version. This is a dependency check, not a usage-frequency check — if it's in `dependencies`, emit it.

#### Form library + validation

Check `dependencies` for form state management:

- `formik`, `react-hook-form`, `@tanstack/react-form`
- `vee-validate`, `@vuelidate/core`
- `@angular/forms` (reactive vs. template-driven)
- `svelte-forms-lib`, `felte`

And validation libraries: `yup`, `zod`, `joi`, `@valibot/valibot`, `superstruct`, `class-validator`.

If both a form library and validation library are present, emit them as a pairing.

#### State management

Check `dependencies` for state management:

- `redux`, `@reduxjs/toolkit`, `zustand`, `jotai`, `recoil`, `@tanstack/react-query`
- `pinia`, `vuex`
- `@ngrx/store`, `@ngxs/store`, `@rx-angular/state`
- `svelte/store` (built-in)

Emit the library name. If `@tanstack/react-query` (or similar data-fetching-as-state libraries) is present alongside a traditional state manager, note both and their distinct roles.

#### Routing

Check `dependencies` for routing:

- `react-router-dom`, `@tanstack/router`, `next/navigation`, `wouter`
- `vue-router`, `@nuxt/router`
- `@angular/router`
- SvelteKit's file-based routing (check for `@sveltejs/kit` in dependencies)

Emit the router and note whether route definitions are centralized (a routes file) or file-based.

#### Data fetching convention

Detection varies by framework:

- **React:** Find the most-imported custom hook in `src/` by grep count of `import { ... } from` statements targeting project-internal paths (not node_modules). Then check whether other hooks import it and re-export a narrower, domain-specific interface. This layered pattern (low-level fetch hook → domain hooks like `useFleets`, `useDevices`) is the most common convention that agents violate by calling the low-level hook directly.
- **Vue:** Find the most-imported composable (`use*` functions) from a `composables/` or `hooks/` directory. Look for domain-specific composables that wrap a shared data-fetching composable.
- **Angular:** Find injectable services that wrap `HttpClient`. Look for domain-specific services that extend or delegate to a base API service class.
- **Svelte:** Find shared load functions or stores that wrap `fetch`. Look for domain-specific wrappers in `lib/` or `stores/`.

If a layered pattern exists and meets the confidence threshold, document it with:
1. The low-level hook/composable/service name and path
2. An example domain wrapper (shortest one found)
3. A short code example (5–10 lines)

The React heuristics are the most validated. Vue/Angular/Svelte heuristics are sound but less battle-tested — lean on the confidence threshold rather than assuming the pattern.

#### URL-as-state-source

Grep for framework-appropriate URL state patterns:

- React: `useSearchParams` from `react-router-dom`
- Vue: `useRoute().query` or `useRouter().push({ query: ... })`
- Angular: `ActivatedRoute.queryParams` or `queryParamMap`
- Svelte: `$page.url.searchParams`

If used in 5+ distinct feature directories, this is the project's convention for filter/sort state. Document it explicitly — agents default to React state or local variables for filters, which breaks URL-shareable views.

#### Pagination model

Search API response types, fetch hooks, or service return types for cursor-based pagination fields: `continue`, `cursor`, `nextToken`, `pageToken`, `endCursor`, `after`, `startAfter`.

If found, explicitly state the pagination model. Agents default to offset-based pagination (`page`, `offset`, `skip`) and will generate incorrect pagination code if the API uses cursors.

This detection is framework-agnostic.

#### Permissions / RBAC

Search for permission-checking patterns by framework:

- **React:** Hooks like `usePermissions`, `useAuth`, `useAccess`, `useRBAC`. HOC wrappers like `withPermission`. Context providers for auth state.
- **Vue:** Navigation guards checking permissions. Directives like `v-permission`, `v-can`. Composables like `usePermissions`.
- **Angular:** Route guards (`CanActivate`, `CanActivateChild`). Structural directives like `*hasPermission`, `*isAuthorized`.
- **Svelte:** Store-based permission checks. Layout-level auth guards.

If a consistent pattern exists, document the hook/guard/directive name and show a brief usage example.

### Step 3: Format Findings

Structure all findings as content blocks ready for insertion into AGENTS.md's Architecture section. Use this order:

1. Restricted Patterns table (from Step 1)
2. Generated Files list (from Step 1)
3. Testing Philosophy (from Step 1)
4. i18n Rules (from Step 1)
5. Detected Patterns with code examples (from Step 2, only those meeting the confidence threshold)
6. Reference implementations — for each documented pattern, include the file path of the best example to imitate

**Supplementary file decision:** If the total frontend content exceeds approximately 150 lines, recommend splitting:
- Core constraints (all Step 1 findings) stay inline in AGENTS.md's Architecture section
- Pattern documentation (Step 2 findings + reference implementations) go in a separate file (e.g., `UI-ARCHITECTURE.md`) referenced from AGENTS.md with a brief note: `For frontend patterns and reference implementations, see [UI-ARCHITECTURE.md](UI-ARCHITECTURE.md).`

If the content fits within ~150 lines, keep everything inline in the Architecture section.

## Output

One or more Markdown sections for `update.md` to incorporate into AGENTS.md's `## Architecture` section. Each section starts with a `###` heading (to nest correctly under `## Architecture`) and is valid Markdown ready for direct insertion — no wrapping or reformatting needed.

If the supplementary file threshold is exceeded, output two artifacts:
1. A brief `###` section for AGENTS.md containing the constraint tables and a reference link to the supplementary file
2. The full supplementary file content (e.g., `UI-ARCHITECTURE.md`) as a standalone document with its own `#` heading
