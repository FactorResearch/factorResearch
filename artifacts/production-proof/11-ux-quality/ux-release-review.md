# UX Release Review

**Review date:** 2026-07-16  
**Decision:** automated UX release gates passing; human physical-device and assistive-technology sign-off remains explicit.

## Required evidence

- Functional release gate: `scripts/release-gate.sh`.
- Core Web Vitals budgets: LCP p75 ≤ 2.5s, INP p75 ≤ 200ms, CLS p75 ≤ 0.1, segmented by normalized route and mobile/tablet/desktop.
- First-useful-result and task budgets: `config/ux_performance_budgets.json`.
- First-party bundle budget report: `/tmp/ux-performance-budget-report.json` in CI artifacts.
- Accessibility and responsive audit: `artifacts/production-proof/10-accessibility/accessibility-audit-results.json`.
- Visual regression: design-system workshop artifacts uploaded by PR CI.
- Usability tasks and findings: this directory's study and findings log.

## Privacy review

- Product metadata drops symbols, portfolio names, queries, prices, values, shares, formulas, weights, account data, and secret-bearing keys.
- Web Vitals contain only metric, bounded value, normalized route, device class, and navigation type.
- PostHog autocapture and session recording are disabled.
- Optional replay requires an explicit flag and applies strict page-level masking before initialization.
- Analytics opt-out prevents Web Vitals and UX event collection.

## Release rule

Any functional failure, WCAG violation, page overflow, visual regression, first-party asset-budget failure, or material p75 Web Vitals regression blocks release or requires an explicit owner-approved exception with expiry and linked issue.

