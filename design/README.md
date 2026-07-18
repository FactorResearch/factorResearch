# Cenvarn Design Bible

Version: 1.1 — mirrored from the current Notion design source.

This folder is the single source of truth for every visual and interaction decision
inside Cenvarn.

## Rules

Codex must always read documents in this order:

1. DESIGN_SYSTEM.md
2. COMPONENT_LIBRARY.md
3. IMPLEMENTATION_RULES.md
4. RESPONSIVE.md
5. ACCESSIBILITY.md
6. ANIMATIONS.md
7. The approved AI-readable HTML prototype attached to the Notion design page.

Never redesign.

Never simplify.

Never remove information.

Never create new components unless instructed.

If anything conflicts:

DESIGN_SYSTEM.md wins.

If a local mirror differs from Notion,

Notion wins and the local mirror must be updated before implementation.

If uncertainty exists,

ask before implementing.

---

## Source of truth

The current Notion page is **New UI Design Implementation Plan**. Its attached HTML
prototype is the canonical visual reference. The retained local Markdown files are
execution mirrors for repository tooling. The former generic `SPEC.md` and old
design-system wording are not authoritative.

## Folder Structure

design/

prototype/

desktop/

tablet/

mobile/

---

## Current Prototype Status

Landing Page

Authentication

Dashboard

Screener

Analyze

Portfolio

Factor Lab

Settings

Billing

Print Layout

Error Pages

Loading States

---

## Development Philosophy

Cenvarn is a professional financial research platform.

Every decision should increase:

• Trust

• Information density

• Speed

• Consistency

• Accessibility

Never sacrifice financial information for aesthetics.
