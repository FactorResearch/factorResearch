# Factor Research design engine

ISSUE_075 establishes `codes/app_modules/design_system` as the production UI contract. It complements the clean-boundary rules in `docs/architecture.md`: tokens and schemas are framework-neutral; Dash adapters live in primitives, financial components, states, and layouts; pages compose these modules without moving financial calculations into presentation code.

## Source of truth and themes

`tokens.py` is the typed source for semantic color, typography, spacing, borders, radii, elevation, layering, breakpoints, containers, motion, density, touch targets, charts, and tables. Run `PYTHONPATH=. python scripts/generate-design-tokens.py` after changing it. Never edit `_design_tokens.generated.scss` manually or introduce a second SCSS token definition.

Dark is the default theme. Light overrides use the same variable names. The application persists `light`, `dark`, or `system` through user settings and `localStorage`, responds to live system-preference changes, and exposes `data-theme` for components and charts. `prefers-contrast` and `prefers-reduced-motion` are centralized in the engine stylesheet.

To add a token, choose an intent-based name, add it to the appropriate `TokenGroup`, add a light override only when the default is unsuitable, regenerate, and extend the propagation test. Raw color, radius, and z-index additions outside approved token sources fail the design-system check. Chart and third-party exceptions require an inline `design-system-exception:` reason and must also be registered in the migration inventory.

## Components and variants

Use `primitives.py` for buttons, links, form fields and controls, cards, badges, alerts, overlays, tabs, menus, tables, pagination, loading indicators, status regions, empty states, and notifications. Each component owns its semantic roles, touch target, focus-visible treatment, disabled/loading behavior, and theme behavior. Add a variant only when it represents reusable intent; implement it through a modifier class and semantic tokens, then add it to `catalogue.py` and the accessibility/visual contract tests.

Use `financial.py` for currency, percent, ratio, multiple, compact-number, metric, score, verdict, delta, freshness, missing-data, and confidence presentation. Financial direction includes a shape or word cue, never color alone. Add a formatter by extending `FinancialFormat`, defining null and negative behavior, and adding boundary tests.

Use `layouts.py` for containers, stacks, clusters, responsive grids, reading/sidebar arrangements, headers, sticky regions, and mobile actions. Page modules supply content; breakpoint rules remain in the layout engine.

## Async sections and schema composition

`UIState` is the shared state vocabulary: idle, loading, refreshing, partial, success, empty, stale, warning, recoverable error, unavailable, and disabled. `analysis_section` owns skeleton/progress choice, stale-content placement, retry placement, and announcements. Optional failures stay local to their section.

For repeated sections, define a `SectionDefinition` with a stable ID, component type, priority, data dependency, loading/error policy, entitlement, responsive span, deferral and stale rules, and analytics ID. Register focused renderers in `SectionRegistry`. Renderers receive already-calculated data; business calculations must remain in services/domain modules. Unique workflows should remain explicit compositions.

## Catalogue, tests, and review

`catalogue.py` is the project-native workshop. `catalogue_matrix()` renders light/dark and mobile/desktop contexts with long text, financial semantics, primitive variants, and every asynchronous state. Tests verify keyboard/focus contracts, theme propagation, schema validation, accessibility semantics, and deterministic visual contracts. The browser accessibility audit covers WCAG 2.2 A/AA and primary application breakpoints.

Run the workshop with `PYTHONPATH=. python scripts/design-system-workshop.py`. With WebDriver on port 4444, `npm run audit:design-system` runs axe and compares real browser screenshots for light/dark at mobile/desktop sizes. More than 1% materially changed pixels fails. Set `UPDATE_VISUALS=1` only to approve an intentional baseline change during review; candidate images are uploaded by CI.

Before review, run `./scripts/release-gate.sh`. A pull request changing tokens or components must include the generated CSS, catalogue coverage, contract snapshots, and an explanation for intentional visual changes.

## Reference migrations

Analyze composes its ordered sections from typed definitions inside the responsive analysis layout. Portfolio uses the shared container/grid, metric formatters, non-color delta, empty state, mobile action region, and responsive table. These are the reference patterns for ISSUE_068–074; subsequent screens should migrate incrementally rather than receive page-specific replacements.
