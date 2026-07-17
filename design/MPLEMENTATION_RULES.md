# Implementation Rules

These rules are mandatory.

## Never redesign.

Implement exactly.

---

Reuse existing components.

Never duplicate.

---

Never hardcode spacing.

Use design tokens.

---

Never hardcode colors.

Use design tokens.

---

Never hardcode font sizes.

Use typography tokens.

---

Every loading state must exist.

---

Every error state must exist.

---

Every empty state must exist.

---

Every asynchronous action must support retry.

---

Desktop

Tablet

Mobile

must all behave consistently.

---
# Backend Contract

The backend is the source of truth.

The frontend exists to present backend data.

Never redesign the backend data model from the frontend.

Never invent calculations that do not exist.

Never duplicate backend business logic in the frontend.

---

# Card Contract

The backend defines the available cards.

The mock defines the preferred layout.

If the backend contains a card that does not appear in the mock:

- Keep the card.
- Integrate it naturally into the page.
- Do not delete backend functionality simply because the mock predates it.

If the mock contains a card that the backend does not currently provide:

- Do not invent placeholder data.
- Do not fabricate calculations.
- Omit the card until backend support exists unless explicitly instructed otherwise.

Never create new financial cards unless requested.

Never remove existing backend-supported cards unless explicitly instructed.

Information density is a competitive advantage.

The goal is to organize information better, not reduce it.

Do not hard code any data into the cards, all datas in front end come from backend

---

# Screener Rules

The Screener page contains two contextual panels below the table.

Left panel

Quick Overview

This replaces the existing Quick Peek implementation.

Right panel

Score Development

Displays historical score trend.

Default state

- Hidden when no company is selected.

Selection

- Selecting a company populates both panels.

Persistence

- Panels remain visible until another company is selected.

Navigation

- These panels belong only to the Screener page.
- Navigating to Analyze, Portfolio, Factor Lab, or other pages removes them from view.
- Returning to the Screener restores the most recently selected company if it still exists in state.

Never move these panels elsewhere.

---

# Analyze Navigation

The stock search is global.

Users should never navigate to Analyze before searching.

Desktop

Global Analyze Search lives in the sidebar.

Tablet

Global Analyze Search remains persistently visible.

Mobile

Global Analyze Search lives in the header.

Selecting a ticker immediately navigates to its Analyze page.

Minimize the number of clicks required to start research.

---

# Portfolio Rules

The mock may show multiple Monte Carlo charts.

The backend currently supports one authoritative Monte Carlo simulation.

Never duplicate Monte Carlo simply to match the mock.

Reuse the existing simulation.

Improve presentation only.

Do not invent additional simulations.

---

# Design Fidelity

The HTML prototype is a visual target.

Not every backend feature will exist in the prototype.

Not every prototype element will exist in the backend.

When conflicts occur:

1. Preserve backend functionality.
2. Preserve the intended visual layout.
3. Integrate existing features cleanly.
4. Ask before removing functionality.

Never simplify the application merely to match a static mock.

Cenvarn is a financial research platform, not a marketing website.

Completeness, trust, and clarity always take priority over minimalism.
---
# Existing Features

Before removing any component, verify that:

- it has no backend dependency
- it is not populated by an API
- it is not required by another page
- it is not planned by an existing issue

If any of the above are true,

integrate the component into the new design.

Do not remove it.

When uncertain,

ask before deleting.
---

When uncertain

STOP

Ask

Do not guess.
