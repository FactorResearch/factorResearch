# Implementation Rules

This file is the corrected local filename for the implementation rules retained in
the Notion design source. Keep `MPLEMENTATION_RULES.md` only as a compatibility
mirror until repository references have migrated.

## Mandatory rules

- Implement the approved prototype faithfully. Do not redesign or simplify it.
- Reuse existing components and token sources; do not duplicate components.
- Do not hardcode colors, spacing, radii, font sizes, weights, or line heights.
- Use modern Sass modules and the approved centralized responsive mixins.
- Preserve backend-supported functionality and do not invent financial data or
  calculations in presentation code.
- Integrate backend-supported cards even when the visual mock does not show them.
- Every asynchronous action needs loading, success, failure, and retry behavior.
- Desktop, tablet, and mobile layouts must remain functional and accessible.
- WCAG 2.2 AA, keyboard access, visible focus, reduced motion, and 44px touch
  targets are required.

When uncertain, stop and consult the Notion source rather than guessing.
