# Portfolio page mockup migration and defect record

## Scope

Rebuild the Dash portfolio tab around `mockup/preview.html`'s `#page-portfolio`
hierarchy while preserving the existing user-owned holdings, cached research,
comparison, simulation, provenance, and background-job contracts. Add canonical
portfolio URLs and repair the Dash 4 progress-value incompatibility exposed by
portfolio simulation.

## Defects and root causes

### Attempt 1 — 2026-07-19

1. **Simulation returns the user to Analyze.** A Portfolio tab click changes only
   component visibility, leaving an earlier analysis pathname in `dcc.Location`.
   Starting a simulation writes `upgrade-funnel-store`, which retriggers global
   navigation. Navigation then treats the stale analysis pathname as canonical
   and shows Analyze again.
2. **Simulation progress crashes React.** The shared `progress` primitive passes
   an integer to `html.Progress.value`. Dash 4.4 declares that property as a
   string, so the initial zero-percent job snapshot fails prop validation.
3. **Portfolio has no durable page state.** Reloading or sharing the page cannot
   restore the selected portfolio because no portfolio route is recognized or
   synchronized with the active dropdown.
4. **The current hierarchy does not match the approved mockup.** Research health,
   summary metrics, actions, and holdings are rendered as a long sequence rather
   than the mockup's summary-first dashboard. The visual migration must adapt to
   production data; it must not fabricate mockup values or move calculations into
   the presentation layer.

No earlier implementation attempt for these four portfolio defects is recorded.
Future attempts must add changed evidence here before repeating an approach.

### Attempt 2 — 2026-07-19

**Observed behavior.** Changing the selected portfolio route while partway down
the Portfolio page moves the viewport to the top. The dashboard also repeats
the same score, coverage, concentration, and weak-link concepts in its metric
strip, analysis card, and dedicated weak-link card.

**Affected journey and layers.** The defect affects portfolio selection and
holding-refresh journeys across the client-side tab/scroll coordinator, Dash
URL and dropdown callbacks, callback-rendered portfolio presentation, and
portfolio SCSS composition. Persistence, financial formulas, providers, and
cached analysis contracts are not affected.

**Confirmed evidence.** A headless Firefox run on `/portfolio/test` remained at
`scrollY=900` for six seconds with no `portfolio-content` mutations, disproving
the background interval as the cause. Dispatching a route change to
`/portfolio/t2` immediately produced `scrollY=0` and two content mutations.
The existing Screener scroll-restoration callback explicitly calls
`window.scrollTo(0, 0)` whenever either Analyze or Portfolio is visible; the
callback cannot distinguish a real tab transition from a URL-driven style
refresh within the already-visible Portfolio tab. DOM inspection found exactly
one portfolio root, metric strip, content grid, analysis card, and holdings
card, disproving a duplicated React tree. The repeated appearance is semantic:
the renderer presents aggregate score/coverage/concentration twice and weak-link
content in both the analysis observations and a separate card. Finally,
`refresh_portfolio_dropdowns` returns the unchanged active value on refresh,
which retriggers the full holdings renderer in addition to its direct refresh
input. Post-fix screenshot inspection also confirmed that CSS Grid's default
cross-axis stretching makes short Allocation and Weak-link cards fill the height
of taller neighboring cards, producing large empty surfaces that resemble
duplicated panels even though DOM counts remain one.

**Smallest candidate fix.** Track the previously visible research tab in the
existing client-side scroll coordinator and reset to the top only when the
visible tab actually changes. Preserve Screener's saved-position behavior. On a
portfolio data refresh, return `dash.no_update` for an already-valid active
portfolio so the callback does not create a duplicate render. Keep aggregate
metrics in the summary strip, risks in the analysis card, and weak-link detail
in the dedicated weak-link card; do not alter calculations or source data.

**Regression and acceptance.** Source-level callback tests must require the
same-tab guard and unchanged-selection `no_update` behavior. Renderer tests must
prove that one dashboard root remains and that the removed duplicate regions do
not return. Browser verification must show that a portfolio-to-portfolio route
change preserves a non-zero scroll position, while switching from another tab
to Portfolio still starts at the top. No Dash error card or horizontal overflow
may be introduced.

**Attempt status.** Retained. The shared scroll coordinator now compares the
previous and current visible tab before resetting the viewport; unchanged
portfolio selections use `dash.no_update`; and repeated aggregate/weak-link
regions were removed from the analysis card. This is not a repeat of attempt 1:
the new evidence identified the shared scroll coordinator and semantic
composition, neither of which was changed by the route/progress repair.
Dashboard cards now align to the start of their grid row so independent short
cards do not create false duplicate/empty surfaces.

**Validation result.** The focused portfolio, progressive-disclosure,
responsive-workflow, callback-registration, direct-link, simulation-limit, and
fault-tolerance tests passed (`26 passed`). Ruff, frontend JavaScript syntax,
generated `style.css` parity, and `git diff --check` passed. In Firefox, the
previously failing `/portfolio/test` to `/portfolio/t2` transition preserved
`scrollY=900` through the content replacement; a real Portfolio to Analyze tab
transition reset to `scrollY=0`. Both states had zero Dash error cards and one
portfolio root/grid. The full suite reported `1293 passed, 2 skipped, 9 failed`;
the nine failures are unchanged repository baseline issues outside this defect.
The aggregate style command still stops on the pre-existing
`company_analysis.css` compiler-output mismatch after confirming `style.css`
matches its generated output.

### Attempt 3 — 2026-07-19: allocation, disclosure, and weak-link semantics

**Requested behavior.** Replace the Allocation text-only list with the donut
visual shown in `mockup/preview.html`; make Data trust a keyboard-operable
accordion that is closed on initial render; remove the repeated Portfolio
research snapshot/health card; move Holdings below Allocation; and stop placing
Weak link beside Holdings. Preserve live portfolio data and editing controls.

**Affected journey and layers.** This slice affects the callback-rendered Dash
portfolio composition, the shared Data trust presentation primitive, Plotly
allocation rendering, portfolio SCSS, and the domain weak-link classification
returned by `codes.portfolio.analyze_weak_links`. It does not change portfolio
ownership, persistence, provider calls, cache keys, backtest windows, CAGR,
counterfactual return calculations, or stored data.

**Confirmed facts.** The current Allocation card renders only a sector list.
The content grid places Holdings in a two-column span and Weak link in the third
column on the same row. The Portfolio analysis card contains a “Portfolio
research snapshot” summary derived from the same score, coverage,
concentration, and sector inputs already shown elsewhere. Data trust is always
expanded inside that repeated card. Separately, the domain engine can assign
`"weak link"` to every holding that crosses an absolute drag threshold even
though its response already exposes one `weakest` holding based on the
counterfactual SPY replacement test. That mixes two meanings: “an
underperformer” and “the single largest marginal drag.”

**Resolved design.** The summary metric strip remains the single owner of total
value, research score, coverage, and concentration. The snapshot/health card is
removed rather than renamed. Data trust becomes an independent native
`<details>` disclosure, closed by default, with the same provenance and
missing-data content. The first content row contains Allocation and the
research weak-link review card. Allocation uses a responsive Plotly donut and
retains a visible numeric sector legend so values are not communicated by color
alone. Holdings spans the full grid width directly underneath. Empty and
unknown-sector allocation data remain explicit.

**Resolved weak-link methodology (version-preserving classification repair).**
The existing counterfactual formula remains authoritative:

`swap_delta_pct = return(portfolio with holding replaced by SPY) - actual portfolio return`

A positive value means replacing that holding with SPY would have improved the
portfolio over the aligned backtest period. A portfolio may have at most one
`"weak link"`: the holding with the uniquely largest positive
`swap_delta_pct`. Other holdings that cross the existing material-drag
threshold are classified as `"drag"`; they are not co-equal weak links. If the
largest rounded counterfactual impact is non-positive, there is no weak link.
If multiple holdings tie for the largest positive impact at the calculation's
0.01 percentage-point precision, there is no *unique* weak link and each tied
underperformer remains a drag. Contributor and neutral thresholds remain
unchanged. This repair changes only classification labels and singular
selection; it does not change prices, weights, returns, CAGR, basis-point drag,
rounding, currency assumptions, or point-in-time inputs.

The pre-simulation research card is explicitly a different, display-only
signal: it may show one uniquely lowest researched composite score among at
least two scored holdings. Tied lows and portfolios with fewer than two scored
holdings show that no unique research weak link is available. It must not claim
to be historical performance drag.

**Failure and accessibility behavior.** A missing sector is grouped as
`Unknown`, never coerced into another sector. A zero-value portfolio shows an
allocation empty state rather than a misleading chart. The donut has a text
summary/legend and accessible label; Data trust uses native Summary/Details
keyboard semantics and no `open` attribute on first render. Optional analysis
enrichment failure must still leave Holdings editable. Plotly failure remains
section-local and must not remove Holdings.

**Regression plan and acceptance criteria.** Add deterministic tests proving:

- the allocation card contains a donut graph and a visible sector-value legend;
- Data trust renders as closed Details while existing non-collapsible callers
  retain their contract;
- the repeated snapshot/health card is absent;
- Weak link precedes a full-width Holdings row rather than sharing its row;
- two material underperformers produce at most one weak-link verdict;
- tied largest positive impacts produce no arbitrary unique weak link;
- no-positive-impact portfolios produce no weak link;
- existing contributor/neutral behavior and comparison consumers remain valid.

Browser acceptance requires one portfolio root, no Dash error card, a visible
donut with non-zero width and height, a closed Data trust disclosure on load,
Holdings below the first chart row, no horizontal overflow at desktop and mobile
widths, and retained edit/remove/simulation controls.

**Attempt status.** Planned and documented before code. If implementation is
interrupted, resume by adding the regression tests above, observe their expected
failures, update comments/docstrings first, and then make only the documented
changes. Do not restore the prior text-list/snapshot layout unless new evidence
or changed acceptance criteria is recorded here.

**Implementation check 3A.** The first focused run produced the five expected
pre-implementation failures. After the documented changes, four were resolved
and the renderer test exposed a new local construction error: `_chart_layout`
already includes `margin`, while the donut passed a second `margin` keyword to
`Figure.update_layout`, raising `TypeError` before the portfolio tree could
render. Retain the shared chart layout, override its margin in a copied mapping,
and pass each Plotly layout key once. This is a rejected call-construction
attempt, not evidence against the donut design or the prior chart/CSP repairs.

## Intended contract

| Concern | Behavior |
| --- | --- |
| Portfolio workspace | `/portfolio` opens the Portfolio tab. |
| Selected portfolio | `/portfolio/{name}` uses a URL-encoded, validated portfolio name. |
| Ownership | A route may select only a name returned by `list_portfolios` for the current user. Unknown names do not disclose whether another user owns them. |
| Selection synchronization | A Portfolio tab click or active selection writes the canonical route; a direct route restores the active dropdown. |
| Simulation | Starting, polling, cancelling, or completing a job leaves the Portfolio tab active. |
| Progress | The primitive accepts numeric percentages internally and serializes the HTML `value` and `max` properties as strings for Dash 4.4. |
| Metrics | Total value, aggregate research score, research coverage, and concentration are derived from existing holdings and cached analyses. Missing research remains unavailable, never zero-filled. |
| Layout | Heading and actions, four-metric strip, closed Data trust disclosure, allocation/weak-link pair, full-width holdings row, and independent simulation results follow the mockup's hierarchy and responsive collapse. |

## Boundaries and failure behavior

- Portfolio names continue to use the existing allow-list and 32-character limit.
- URL decoding is followed by the same portfolio-name validation used at write
  boundaries. Invalid encodings and names resolve to no active portfolio.
- The route never loads a portfolio before checking it against the current
  user's list.
- Cached analysis enrichment is optional. Holdings remain editable if enrichment
  or allocation metadata is unavailable.
- Simulation failures remain section-local and do not replace the dashboard.
- No financial formula, provider request, persistence schema, or cache format is
  changed by this migration.

## Acceptance checks

- [ ] `/portfolio` and a valid `/portfolio/{name}` render the Portfolio tab on a fresh load.
- [ ] Selecting a portfolio updates the pathname using safe URL encoding.
- [ ] An unknown or invalid route cannot select or reveal a portfolio.
- [ ] A simulation job can render zero-percent progress without a React prop error.
- [ ] Simulation store updates cannot switch a portfolio route to Analyze.
- [ ] The dashboard uses only existing holdings and cached analysis values.
- [ ] Holdings editing, removal, comparison, simulation, cancellation, and empty states retain their callback IDs.
- [ ] The layout collapses without horizontal page overflow from 320 px upward.
- [ ] Focus, headings, status announcements, tables, and reduced motion remain accessible.
- [ ] Focused unit/regression tests, Sass compilation, and whitespace validation pass.

## Rollout and rollback

This is a backward-compatible presentation and client-route change. Existing
in-memory/cache portfolio records remain unchanged. Rollback consists of restoring
the prior portfolio renderer/styles, removing portfolio route synchronization,
and restoring the previous progress primitive. No migration or data recovery is
required.

## Design references loaded

The repository UI, frontend, accessibility, security, testing, Git, API, and
observability standards were loaded before implementation. The Architect UX,
UI Designer, and UX Researcher design-agent references required by the frontend
standard were also reviewed before code generation.
