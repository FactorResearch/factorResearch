# Phase 10 UX and Accessibility Evidence

**Status:** Automated WCAG 2.2 and responsive audit expanded; full browser/device and manual assistive-technology certification remains open.
**Evidence date:** 2026-07-14

## Automated Contract

- Firefox audits screener, analyze, and portfolio at desktop, tablet, and mobile widths.
- Every route/width is tested in light and dark themes against WCAG 2.0, 2.1, and 2.2 A/AA axe rules.
- Horizontal document overflow fails the audit, including a 200% mobile scenario.
- The audit verifies a reduced-motion media rule exists.
- Machine-readable output is retained as `axe-results.json`; a nonzero exit blocks certification.

## Manual and External Gates

- [ ] Chromium current/previous, Firefox current/previous, and Safari/WebKit current/previous.
- [ ] Physical iOS Safari and Android Chrome across representative low/mid/high-tier devices and both orientations.
- [ ] Keyboard-only focus order, skip/navigation behavior, dialogs, accordions, quick peek, chart expansion, and portfolio simulation.
- [ ] VoiceOver, NVDA, and TalkBack names, roles, states, announcements, and reading order.
- [ ] Light, dark, forced colors, reduced motion, 200% zoom, text spacing, and touch targets.
- [ ] Slow/intermittent network, stale data, errors, offline shell, and expired service-worker behavior.
- [ ] Five-stock rapid-analysis workflow and Core Web Vitals p75 measured on representative mobile traffic.

Automated axe success does not certify WCAG 2.2 AA without the manual assistive-technology and supported-device matrix.
