# Cenvarn UI Redesign Migration Plan

## Purpose

Migrate the live Dash application toward the approved `mockup/preview.html`
visual baseline in small, verifiable slices. The mockup defines visual intent;
the existing Dash IDs, callbacks, services, and live financial data remain the
behavioral source of truth.

## Loaded design authority

- Notion: **New UI Design Implementation Plan**.
- Notion: centralized design-engine and incremental-migration requirements.
- Repository: `docs/frontend.md`, `docs/ui.md`, and `docs/accessibility.md`.
- Repository: `design/IMPLEMENTATION_RULES.md`, `design/ACCESSIBILITY.md`, and
  `design/SPEC.md`.
- Design-agent instructions loaded before implementation:
  `design-ux-architect.md`, `design-ui-designer.md`, and
  `design-ux-researcher.md`.
- Canonical visual reference: `mockup/preview.html`.

## Non-negotiable boundaries

1. Do not replace live data with mockup sample values.
2. Do not move financial calculations into presentation code.
3. Keep existing callback IDs stable unless a migration includes a regression
   test and an intentional compatibility plan.
4. Keep dynamic callback inputs in the initial Dash layout.
5. Use centralized SCSS tokens for new visual decisions. Do not delete legacy
   partials until their selectors have replacement coverage and tests.
6. Support desktop, tablet, mobile, light, dark, loading, empty, stale,
   degraded, and error states.
7. Do not call a slice complete without rendered-layout evidence and automated
   checks.

## Slice order

### Slice 0 — Baseline and shell contract

- Record current layout structure and known runtime errors.
- Verify all callback input IDs exist exactly once in the initial layout.
- Define shell regions: rail, top bar, workspace, mobile navigation, and
  profile/pricing access.
- Acceptance: no overlap, clipped content, inaccessible navigation, or broken
  callback inputs at supported viewport widths.

### Slice 1 — Application shell only

- Implement the rail/top bar using stable existing navigation IDs.
- Keep all view bodies visually unchanged.
- Acceptance: navigation works, content begins after the rail, mobile layout
  does not retain desktop rail geometry, and keyboard focus is visible.

### Slice 2 — Analyze reference composition

- Map existing live Analyze sections into the mockup's hierarchy.
- Preserve current loading, partial failure, and provenance behavior.
- Acceptance: live ticker search and analysis callbacks still work; each
  independent card can degrade without blanking the page.

### Slice 3 — Portfolio reference composition

- Map live metrics, allocation, holdings, and simulation states.
- Preserve entitlement, cancellation, and stale-result behavior.

### Slice 4 — Screener and Factor Lab

- Apply the same card, table, status, and responsive primitives.
- Preserve filter, paging, factor-weight, and backtest behavior.

### Slice 5 — Cleanup

- Remove obsolete SCSS only after selector inventory, compiled-style parity,
  accessibility checks, and targeted visual checks pass.

## Shell acceptance checklist

- [ ] Desktop rail matches the mockup's proportions and does not cover content.
- [ ] Top bar remains usable at widths from 320px through desktop.
- [ ] Navigation has semantic labels, keyboard operation, selected state, and
  visible focus.
- [ ] Profile and pricing remain reachable.
- [ ] Main content has one authoritative width and gutter system.
- [ ] No page-specific raw palette, radius, breakpoint, or typography values
  are introduced outside the centralized foundation.
- [ ] `assets/style.css` is regenerated from `assets/style.scss`.
- [ ] Browser/layout evidence is captured for desktop, tablet, and mobile.
- [ ] Targeted regression and accessibility checks pass.

## Stop conditions

Pause and fix the current slice if any of these occur:

- content is hidden behind the rail or top bar;
- navigation IDs are duplicated or absent from the initial layout;
- a viewport requires horizontal scrolling for the shell itself;
- a callback error appears after a fresh process restart;
- the visual result cannot be compared against the mockup without guessing.

## Bug screenshot findings — 2026-07-18

- `bug.png` showed a missing `/assets/logo.svg` request. The live asset is
  `logo-icon.svg`; both Dash and standalone shell references now use it.
- Long Screener company and sector text rendered over adjacent columns. The
  table contract now gives those columns bounded widths and ellipsis
  truncation.
- The screenshot was captured from port `8050`, while the validation process
  used the current branch on `8055`; both environments must be restarted after
  compiled CSS or layout changes before visual comparison.

## Canonical mockup contract — `mockup/preview.html`

The prototype is a structural reference, not only a color reference. The
production shell must match these relationships:

- `.app-shell` is a two-column CSS grid: `var(--rail)` (`244px`) and a
  min-width-zero workspace.
- `.rail` is a real sidebar containing brand, analyze search, primary
  navigation, support, and profile/footer actions.
- `.workspace` owns the top bar and all page content. The top bar is not the
  parent of the rail.
- `.topbar` contains mobile brand/search and right-side actions only; primary
  desktop navigation does not live inside it.
- `.bottom-nav` is a real fixed four-item mobile navigation bar and is visible
  below `760px`; the desktop rail is hidden at that breakpoint.
- At `1180px`, the rail contracts to `86px` and hides labels while retaining
  icon navigation. At `760px`, the shell changes to a single-column layout.
- Theme state is controlled by `html[data-theme="light|dark"]`, with explicit
  dark semantic surface, text, border, status, and shadow mappings.
- Standard controls use `40px` minimum height and `4px` radius. Pagination
  controls use `34px`; they must not inherit large table-control dimensions.
- Tables live inside `.responsive-table { overflow: auto; }`; tables have a
  deliberate minimum width and `nowrap` cells so they scroll rather than
  allowing text to overlap neighboring columns.
- Profile/security is a rail action/page workflow, not an opaque legacy popup
  covering the workspace.

### Required production mapping

The shell slice introduces real semantic containers in the Dash layout while
preserving existing callback IDs by moving existing controls into those
containers. CSS-only pseudo-elements and fixed descendants inside a filtered
top bar are explicitly disallowed. Mobile navigation forwards to the existing
Dash tab controls, so tab state has one source of truth and no duplicate IDs.

Table cards, profile/security presentation, and view-specific controls remain
separate migration slices; each needs its own mockup comparison and callback
checks.

The screener slice now follows the mockup's detail pattern: no table-view
chooser, and the selected stock opens a bottom two-card dock with Quick
Overview on the left and recorded Score Development on the right. If fewer
than two score snapshots exist, the chart reports that history is unavailable
instead of fabricating a trend.
