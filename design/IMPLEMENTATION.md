# New UI Implementation Order

## Stage 1 — Freeze the visual contract

- Confirm page hierarchy for Analyze, Screener, Portfolio, and Factor Lab.
- Confirm typography, colors, spacing, radii, borders, and chart treatment.
- Confirm desktop, tablet, and mobile behavior.
- No production page replacement during this stage.

## Stage 2 — Map prototype primitives to ISSUE_075

- Convert CSS variables into centralized design tokens.
- Create shared layout shells, navigation, cards, metric groups, tables, badges, charts, tabs, and controls.
- Keep themes token-driven; do not fork components by theme.

## Stage 3 — Build shared interaction states

- Loading and skeleton states.
- Empty, partial, stale, degraded, and error states.
- Retry at section level.
- Keyboard focus, hover, pressed, disabled, and selected states.

## Stage 4 — Implement pages in order

1. Screener — validates table density, filters, navigation, and responsive list conversion.
2. Analyze — validates financial hierarchy, provenance, charts, and progressive disclosure.
3. Portfolio — validates dashboard composition, simulations, and partial failures.
4. Factor Lab — validates controls, weight editing, validation, and saved configurations.

## Stage 5 — Responsive and accessibility pass

- Desktop: persistent rail and dense research canvas.
- Tablet: compact rail with two-column content where space allows.
- Mobile: bottom navigation, stacked cards, condensed tables, and touch-safe controls.
- Meet WCAG 2.2 AA requirements.

## Stage 6 — Integration and rollout

- Connect real data behind stable view models.
- Add visual regression tests.
- Release behind a feature flag.
- Run old and new layouts in parallel.
- Migrate page by page only after acceptance tests pass.

## Acceptance rule

A screen is complete only when light/dark, desktop/tablet/mobile, loading, empty, error, stale, and partial-failure states are implemented.
