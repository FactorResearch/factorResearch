# Analysis page mockup migration

## Scope

Rebuild the Dash analysis tab to match `mockup/preview.html`'s `#page-analyze` structure while keeping the existing analysis service, provenance, deferred chart loading, portfolio action, and callback contracts.

## Contract and mapping

| Mockup region | Production source / behavior |
| --- | --- |
| Analysis toolbar | Current symbol, company name, watchlist/download affordances; actions remain non-destructive until their callbacks are implemented. |
| Company hero | `symbol`, `name`, `sector`, `market_code`, `price`, `updated_at`, composite score, and verdict from the analysis response. |
| Metric strip | Intrinsic value from the Buffett/Graham result, price gap, quality score, Piotroski score, dividend yield, P/E, and EV/EBIT. Missing values render `N/A`, never zero. |
| Investment highlights | Deterministic conclusions derived from available model data; no invented score values. |
| Four data cards | Valuation, financial health, profitability/quality, and risk fields from the existing normalized response. |
| Sentiment/factor row | Existing bias/regime/market data and factor scores. Partial inputs render `N/A` or an unavailable state. |
| Chart row | Existing deferred `analysis-charts-summary`, `analysis-charts-content`, `analysis-charts-retry`, and resize trigger IDs are retained. |

The renderer must keep `analysis-overview`, `analysis-valuation`, `analysis-accounting`, `analysis-risk`, `analysis-growth`, `analysis-signals`, and `analysis-charts` anchors so browser navigation and existing analytics remain compatible. Legacy disclosure metadata remains available on the corresponding sections, but the visible structure follows the mockup.

## Accessibility and responsive behavior

- Use a single `h1`, then `h2` card headings, with semantic `section`, `article`, `dl`, and `table`/text alternatives for chart content.
- Preserve visible focus, keyboard-accessible controls, status announcements, and independent failure states.
- Layout is fluid from 320px through desktop: hero stacks, metric/data grids collapse, factor cards wrap, and charts become one column without horizontal page scrolling.
- All numeric output uses tabular numerals and all visual status uses text as well as color.
- Respect the existing light/dark semantic tokens and reduced-motion behavior.

## Failure and data rules

- A missing optional field shows `N/A` or “Not available”; it is not silently replaced with zero.
- A chart/provider failure leaves the summary and data cards usable and exposes the existing retry affordance.
- The page does not make a second provider request merely to render the new layout.

## Acceptance checklist

- [ ] Rendered analysis markup follows the mockup region order and classes.
- [ ] All six factor-model boxes from the mockup are present; model-specific cards are not replaced by generic placeholders.
- [ ] Every analysis card has tokenized elevation, keyboard focus, and restrained hover motion.
- [ ] Chart rendering exposes the existing EPS, price, and dividend chart components after the analysis response arrives or the user activates the chart control.
- [ ] All values are sourced from the response and remain safe for partial responses.
- [ ] Existing analysis and chart callback IDs remain present exactly once.
- [ ] Light/dark appearance uses centralized semantic tokens.
- [ ] 320px, tablet, desktop, keyboard focus, and reduced-motion checks pass.
- [ ] Sass compiles, focused analysis tests pass, and the diff has no whitespace errors.

## Rollout and rollback

This is a presentation-only migration: no schema or financial formula changes are planned. Rollback is the prior `_build_analysis_content` implementation plus its existing analysis styles. Keep the previous renderer available in the same commit history until visual and callback checks pass.

## Design-agent prerequisite note

`docs/frontend.md` references three public agency-agent instruction files. They were checked before implementation, but are absent from this checkout and could not be fetched because network name resolution is unavailable. Local repository UI, accessibility, testing, financial, and design-system instructions are therefore the active implementation guidance for this change.
