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

Do not remove financial information.

Information density is a competitive advantage.

The backend feed the front end with cards
in analysis view:
If mock is missing cards that backend need add them

If mock has cards that back end does not remove the cards from front end

Do not invent new card or remove cards because mock does not have them.

in screener view:
we have added two box at the bottom of the table
left box replace the current quick view that we have 
the right box show score improving in a chart view
when app launches and no stock is selected boxes are hidden, once stock is selected boxes get populated and displayed
after that box stays on until next stock is selected,
is user navigate to other pages those boxes only stay in overview page.

---

When uncertain

STOP

Ask

Do not guess.
