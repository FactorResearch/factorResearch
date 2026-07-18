# Cenvarn Design System

This file mirrors the current Notion “New UI Design Implementation Plan” source.
The Notion page and its attached HTML prototype are authoritative when this local
mirror is stale.

## Brand palette

Use these canonical tokens. Do not resample screenshots or introduce page-specific
near-duplicates.

```scss
$cenvarn-midnight: #0e1829;
$cenvarn-gold: #b18a54;
$cenvarn-charcoal: #343435;
$cenvarn-silver: #d9d8d6;
$cenvarn-warm-white: #f3f2f1;
$utility-white: #ffffff;
```

- Canvas: Midnight in dark mode; Warm White in light mode.
- Primary text: Warm White in dark mode; Midnight in light mode.
- Secondary text: Silver in dark mode; Charcoal in light mode.
- Borders and separators: Silver-derived semantic border token.
- Brand accent: Gold, used sparingly for selected states, emphasis, and CTA detail.
- Primary buttons normally use Midnight with Warm White text; Gold is not a broad
  background or a replacement for semantic status colors.
- Gold is approved for emphasis on Midnight, not normal-sized text on Warm White.

## Typography

- Font: `Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- H1: 36px desktop / 28px mobile, weight 700, line-height 1.1.
- H2: 28px desktop / 24px mobile, weight 600, line-height 1.2.
- H3: 22px desktop / 20px mobile, weight 600, line-height 1.3.
- Card title: 18px, weight 600.
- Major metric: 44px desktop / 36px mobile, weight 700.
- Body and form input: 16px, weight 400, line-height 1.5–1.6.
- Labels and metadata: 12px.
- Captions: 11–12px.
- Financial numbers use `font-variant-numeric: tabular-nums`.

## Layout and interaction

- Use the shared SCSS token and mixin architecture; no inline visual styles.
- Standard radii are capped at 4px. Percentage radii are prohibited.
- Use the centralized breakpoint mixins from `assets/_media.scss`.
- Support 320px through 4K without horizontal overflow.
- Every interactive control has visible focus and a minimum 44px touch target.
- Preserve loading, empty, stale, partial-failure, and error states.
- Respect reduced motion and forced-colors modes.
- Use real assets from the approved prototype. Treat the HTML mockup as the layout
  reference, not as permission to invent backend data or duplicate domain logic.

## Source synchronization

Notion is the detailed source of truth. When this system changes, update this file,
the applicable token source, automated checks, and the standards index together.
