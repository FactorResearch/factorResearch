# Pre-launch Critical-workflow Usability Study

**Date:** 2026-07-16  
**Method:** structured expert cognitive walkthrough plus automated keyboard, viewport, accessibility, and interaction contracts. This is the pre-launch baseline; participant sessions remain recurring product research, not a substitute for this release gate.

## Participant profiles represented

- Less-experienced investor: needs a plain-language conclusion, visible caveats, and a recoverable path through missing data.
- Advanced/professional user: needs reporting periods, source category, normalization, methodology, model scope, and efficient comparison controls.

No brokerage credentials, account values, portfolio names, tickers, formulas, or other sensitive financial values were recorded in the study evidence.

## Tasks and completion evidence

| Task | Success condition | Evidence | Result |
|---|---|---|---|
| Identify the conclusion | First Analyze view exposes conclusion and key risk | progressive-disclosure tests | Pass |
| Explain why | Strongest/weakest model contribution and inline methodology are reachable | ISSUE_070 and ISSUE_073 contracts | Pass |
| Identify the weakest factor | Weakest factor appears before optional charts | analysis overview test | Pass |
| Verify freshness | Analysis date, price timing, reporting period, source, currency, normalization, and cache state are visible | trust-panel tests | Pass |
| Compare two companies/configurations | Factor Lab clearly separates custom, default, and benchmark history | custom-model provenance test | Pass |
| Diagnose portfolio risk | Weak link and concentration warning precede optional charts | portfolio hierarchy tests | Pass |
| Recover from a failed section | Failure remains scoped and retry telemetry is emitted without losing usable content | adaptive-loading and telemetry tests | Pass |

## Device and interaction matrix

The automated release evidence covers 320px iPhone-sized, Android-sized, tablet, laptop, wide-desktop, and 200%-zoom layouts in light and dark themes. Keyboard navigation, dialogs, touch-safe controls, chart equivalents, and page overflow are release-blocking checks. Physical-device and assistive-technology certification remains the named human sign-off in the accessibility evidence.

## Research cadence

- Run this task set before every major release.
- Schedule participant sessions with both profiles at least quarterly and after material Analyze or Portfolio information-architecture changes.
- Record task completion, time on task, error/recovery, abandonment stage, and understanding confidence.
- Convert every material finding into the findings log and a numbered tracker issue before release approval.

