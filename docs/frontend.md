# New UI Design Implementation Plan

# Objective

Implement the approved high-fidelity Cenvarn redesign without replacing production pages prematurely.

# Working rule

Design work may continue while platform architecture is being completed. Production implementation must use the centralized design engine from `ISSUE_075` and the code-quality boundaries from `ISSUE_076` and `ISSUE_077`.

# Mandatory AI pre-coding prerequisite

Before writing, modifying, or generating any UI code for this redesign, the AI coding agent must load and read all three design-agent instruction files below into its active working context:

1. [Design UX Architect](https://github.com/FactorResearch/agency-agents/blob/main/design/design-ux-architect.md)
2. [Design UI Designer](https://github.com/FactorResearch/agency-agents/blob/main/design/design-ui-designer.md)
3. [Design UX Researcher](https://github.com/FactorResearch/agency-agents/blob/main/design/design-ux-researcher.md)

This is a blocking prerequisite, not optional reference material.

The AI must:

- Read the complete current contents of all three files before starting implementation.
- Treat their requirements as active project instructions throughout the coding session.
- Re-load them whenever a new coding session, agent, context window, or implementation task begins.
- Apply them together with this page, the approved visual prototype, shared design tokens, `ISSUE_075`, `ISSUE_076`, and `ISSUE_077`.
- Stop before coding if any file cannot be accessed, is missing, or has not been fully loaded.
- State in its implementation notes that all three prerequisite files were loaded before code generation began.

No UI implementation task may be considered ready to start until this prerequisite is satisfied.

# Design source of truth

- AI-readable HTML prototype
- Shared CSS design tokens
- Reusable component markup
- Desktop, tablet, and mobile layouts
- Light and dark themes
- State specifications for loading, empty, stale, partial failure, and error
- Border radius must never exceed `4px`; percentage-based radii are prohibited for standard UI components.

## Typography hard constraints

These values are implementation requirements, not suggestions. Components must use the shared typography tokens; page-specific font sizes, weights, or font-family overrides are prohibited unless explicitly approved in the design system.

### Font family

- Primary UI family: `Inter`, with fallback stack `Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- Do not introduce additional display fonts for headings, cards, navigation, tables, or marketing-style UI inside the product.
- Monospace fonts may be used only for code, raw identifiers, or explicitly technical data fields.

### Required font sizes

| Role | Desktop | Mobile |
| --- | --- | --- |
| Page title / H1 | `36px` | `28px` |
| Section title / H2 | `28px` | `24px` |
| Subsection title / H3 | `22px` | `20px` |
| Card title / H4 | `18px` | `18px` |
| Primary score or major metric | `44px` | `36px` |
| Secondary metric | `24px` | `22px` |
| Body and form input text | `16px` | `16px` |
| Table and dense data text | `14px` | `14px` |
| Buttons | `14px–16px` | `14px–16px` |
| Labels and metadata | `12px` | `12px` |
| Captions | `11px–12px` | `11px–12px` |

### Required weights

- `400` — body copy and supporting text.
- `500` — labels, controls, navigation, and buttons.
- `600` — card titles, section emphasis, and important table values.
- `700` — page headings, primary scores, and critical metrics.
- Weights below `400` are prohibited in the product UI.

### Required line heights

- Page title / H1: `1.1`.
- Section title / H2: `1.2`.
- H3 and H4: `1.3`.
- Body text: `1.5–1.6`.
- Tables and dense data: `1.4`.

### Financial-number formatting

- All financial tables, metric grids, prices, percentages, ratios, scores, and time-series labels must use `font-variant-numeric: tabular-nums`.
- Numeric values must align consistently within columns and cards.
- Do not use proportional numerals where users compare values vertically.

### Typography tokens

The centralized design engine must expose and enforce the following minimum token set:

```css
--font-family-ui: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-size-xs: 12px;
--font-size-sm: 14px;
--font-size-base: 16px;
--font-size-lg: 18px;
--font-size-xl: 22px;
--font-size-2xl: 28px;
--font-size-3xl: 36px;
--font-size-metric: 44px;
--font-weight-regular: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
--line-height-tight: 1.1;
--line-height-heading: 1.2;
--line-height-subheading: 1.3;
--line-height-data: 1.4;
--line-height-body: 1.5;
```

### Enforcement and acceptance criteria

- No arbitrary font-size values may appear in page-level CSS, SCSS, CSS-in-JS, or inline styles.
- No component may bypass the typography tokens.
- Desktop and mobile typography must match the defined roles above.
- Inputs must remain at least `16px` on mobile.
- Automated style checks must flag unauthorized font families, weights, sizes, and line heights.
- Visual regression tests must verify typography across desktop, tablet, mobile, light mode, and dark mode.

# Mandatory SCSS architecture and central-control constraints

All production design work must be implemented in `.scss` files. Plain page-level CSS, inline styles, component-local hard-coded visual values, and CSS-in-JS styling are prohibited unless a documented technical exception is explicitly approved.

The objective is to make every major visual decision globally controllable. A change such as updating all `h4` styles, a breakpoint, a font weight, or a semantic color must require editing one centralized source file rather than touching multiple page or component files.

## Required SCSS structure

The design system must use partials extensively. At minimum, provide centralized partials for:

- `_typography.scss` — font families, type scale, heading roles, body roles, line heights, font weights, and numeric formatting.
- `_colors.scss` — raw palette values, semantic color roles, light-theme mappings, dark-theme mappings, chart colors, warning colors, danger colors, and accessibility-safe contrast pairs.
- `_breakpoints.scss` — all named responsive breakpoints and media-query rules.
- `_spacing.scss` — spacing scale, layout gaps, padding, margins, and density modes.
- `_radii.scss` — border-radius tokens and enforcement of the `4px` maximum.
- `_shadows.scss` — elevation and shadow definitions.
- `_z-index.scss` — centralized layering scale.
- `_functions.scss` — reusable SCSS functions for token retrieval, unit conversion, safe map access, and calculated values.
- `_mixins.scss` — shared mixins for typography, responsive behavior, focus states, truncation, containers, surfaces, interaction states, and accessibility patterns.
- `_themes.scss` — theme generation and semantic token output for light and dark modes.
- `_index.scss` or equivalent forwarding entry point using `@use` and `@forward`.

Feature and component SCSS files may define selectors and component-specific composition, but they must consume the centralized partials rather than define foundational design values themselves.

## Hard-coded values prohibited

No feature, page, layout, or component SCSS file may directly hard-code:

- Font family
- Font size
- Font weight
- Line height
- Text color
- Background color
- Border color
- Chart color
- Shadow color
- Breakpoint width
- Raw `@media` query conditions
- Border radius
- Repeated spacing values that already belong to the spacing scale

These values must come from centralized variables, maps, functions, tokens, or mixins.

## Media-query requirement

All responsive behavior must use the dedicated breakpoint partial and shared media-query mixins.

Raw declarations such as `@media (max-width: 768px)` are prohibited outside the centralized responsive utilities. Components must use named interfaces such as `@include respond-below(tablet)` or the project's approved equivalent.

Breakpoint values must exist in one central map so a future breakpoint change updates the entire product consistently.

## Typography requirement

Heading and text styles must be defined once as semantic typography roles. Components must not recreate `h1`, `h2`, `h3`, `h4`, body, label, caption, table, or metric styling.

The system must support changing every `h4` across the product by editing a single typography partial or token map. The same requirement applies to all other type roles.

Use shared mixins such as `@include type-style(h4)` or an equivalent semantic API. Do not copy a group of font properties into individual component selectors.

## Color requirement

Components must consume semantic roles such as `surface-primary`, `text-muted`, `border-subtle`, `status-warning`, and `status-danger`. Components must never reference raw hex, RGB, HSL, or named colors directly.

Theme differences must be resolved centrally. Component files must not contain separate hard-coded light and dark color values.

## Mixins and functions

Use mixins and functions extensively where they reduce repetition, enforce consistency, or create future control points. Required reusable areas include:

- Typography-role application
- Responsive breakpoints
- Focus-visible states
- Hover, active, selected, disabled, loading, stale, warning, danger, and error states
- Card and surface construction
- Text truncation and multi-line clamping
- Visually hidden content
- Touch-target sizing
- Scrollbar behavior
- Grid and container patterns
- Theme-aware token retrieval
- Safe access to SCSS maps

Do not create abstractions merely to hide a single declaration. Maximize reuse where the same pattern appears across multiple components or where centralized control will be valuable later.

## Module rules

- Use modern Sass modules with `@use` and `@forward`.
- New code must not use deprecated global `@import` architecture.
- Avoid global namespace pollution.
- Avoid circular dependencies between partials.
- Keep tokens and primitive definitions independent from feature and component files.
- Component partials must not import or depend directly on other page-level component partials.

## Required automated enforcement

The build and CI pipeline must reject:

- Raw hex, RGB, HSL, or named color values outside approved color/token partials.
- Unauthorized `font-size`, `font-weight`, `font-family`, or `line-height` literals outside approved typography partials.
- Raw `@media` query conditions outside the breakpoint partial or responsive mixin implementation.
- Radius values outside the radius token file.
- Deprecated Sass `@import` usage.
- Inline style attributes and CSS-in-JS visual declarations in redesigned product pages.
- Duplicate declarations that should use an existing mixin, function, or semantic token.

Use Stylelint and custom rules or scripts where standard rules are insufficient.

## SCSS acceptance criteria

- Changing the centralized `h4` typography role updates every `h4`-equivalent card and component title across the application.
- Changing one named breakpoint updates every component consuming that breakpoint.
- Changing a semantic color updates every relevant component in both light and dark themes.
- No page or component contains raw font, color, weight, radius, or media-query values.
- Repeated multi-property patterns are implemented through shared mixins or placeholders where appropriate.
- All SCSS passes linting, compilation, visual regression, responsive, and light/dark parity tests.
- Code review must reject one-off styling that bypasses the centralized SCSS architecture.

# Mandatory responsive coverage and browser compatibility

Responsive behavior is a release requirement for every redesigned page and component. Styling must remain usable, readable, and visually balanced across viewport widths from `320px` through `4K`, including intermediate widths, unusual aspect ratios, browser zoom, large text, and constrained-height screens.

## Viewport coverage

Every page and reusable component must be designed and tested across the following representative width ranges:

- `320–359px` — smallest supported phones and narrow embedded browser views.
- `360–479px` — standard mobile phones.
- `480–767px` — large phones and small portrait tablets.
- `768–1023px` — tablets and compact windows.
- `1024–1279px` — small laptops and landscape tablets.
- `1280–1439px` — standard desktop and laptop displays.
- `1440–1919px` — large desktop displays.
- `1920–2559px` — full-HD and wide desktop displays.
- `2560–3839px` — QHD, ultrawide, and high-resolution displays.
- `3840px and above` — 4K displays and large presentation surfaces.

These ranges are validation targets, not permission to hard-code raw media queries. All breakpoint values and range logic must remain centralized in `_breakpoints.scss` and exposed through named mixins.

## Responsive implementation rules

- Media-query coverage must be extensive enough to handle every layout edge case required by the component, while avoiding arbitrary one-off breakpoints.
- Breakpoints must be content-driven: add a responsive adjustment when content, controls, charts, tables, labels, or navigation no longer fit correctly—not merely because a popular device width exists.
- Every component must remain functional at every width between `320px` and `4K`, not only at the documented screenshot widths.
- Responsive rules must be nested inside the selector they affect and placed after that selector's base declarations.
- Raw `@media` conditions remain prohibited in page and component files. Use centralized mixins such as `respond-between`, `respond-below`, `respond-above`, `portrait`, `landscape`, `reduced-motion`, `high-contrast`, and `hover-capable`.
- Layouts must support viewport height constraints as well as width constraints, including short laptop screens and mobile landscape orientation.
- Use fluid sizing, `min()`, `max()`, `clamp()`, flexible grids, intrinsic layout, wrapping, overflow controls, and container constraints where supported and appropriate.
- Very wide displays must not stretch reading content, tables, forms, or cards beyond usable scan widths. Use centralized maximum-width and density rules.
- Very narrow displays must not create horizontal page scrolling. Only intentionally scrollable data regions, such as complex tables or charts, may scroll horizontally.
- Tables must have defined responsive behavior: column prioritization, wrapping, horizontal scroll, sticky identifiers, or conversion to mobile list/card views.
- Charts must resize without clipped labels, unreadable legends, overlapping axes, or distorted aspect ratios.
- Navigation, dialogs, dropdowns, tooltips, date pickers, filters, sliders, and menus must remain fully visible and operable near every viewport edge.
- Touch targets must remain accessible and must not overlap at small widths.
- Long company names, localized text, large financial values, negative values, missing values, badges, warnings, and validation messages must be tested for wrapping and overflow.

## Required responsive edge-case testing

Every redesigned page must be tested with:

- Browser zoom at `80%`, `100%`, `125%`, `150%`, and `200%` where supported.
- Increased operating-system text size and browser default font-size changes.
- Short and long content, including unusually long company names and translated strings.
- Empty, loading, stale, partial-failure, retry, permission-denied, and error states.
- Mobile portrait and landscape orientations.
- Desktop windows resized continuously between breakpoint boundaries.
- Touch, mouse, keyboard-only, and mixed-input devices.
- Reduced-motion, forced-colors/high-contrast, and dark/light preference modes.
- Safe-area insets and notched mobile devices.
- Scrollbars present and absent.

## Browser-support compilation requirements

The production stylesheet pipeline must generate the compatibility output required by the project's declared browser-support matrix.

Required tooling and behavior:

- Define the supported browser matrix once through `browserslist` or an equivalent centralized configuration.
- Compile Sass through the approved build pipeline and process the generated CSS with PostCSS and Autoprefixer.
- Include required vendor prefixes automatically; developers must not hand-maintain prefixed duplicates in component files.
- Use a CSS minifier configured not to remove required compatibility fallbacks.
- Provide graceful fallbacks for unsupported modern layout or visual features.
- Order fallback declarations before enhanced declarations so capable browsers receive the modern implementation.
- Avoid relying exclusively on CSS features that fail without fallback in a supported browser.
- Include automated compatibility checks in CI and run cross-browser visual and interaction tests.

## Legacy Internet Explorer policy

The legacy compatibility baseline is **Internet Explorer 11**, not every historical Internet Explorer release. Supporting obsolete versions earlier than IE11 would impose severe security, accessibility, and architecture limitations and is not required.

Where IE11 support is contractually required:

- Core information, navigation, forms, tables, analysis results, and essential actions must remain accessible and operable.
- Enhanced visuals may degrade gracefully when an equivalent modern feature is unavailable.
- CSS Grid, custom properties, `clamp()`, container queries, sticky positioning, modern color functions, and other unsupported features must have explicit fallback strategies where they affect essential use.
- The build may produce a dedicated legacy stylesheet or legacy bundle when necessary rather than weakening the modern stylesheet for every user.
- IE11 compatibility must be tested separately and documented as a constrained experience.

Modern browsers—including current Chrome, Edge, Firefox, and Safari—must receive the full design experience. The supported-version range for each browser must be controlled centrally and reviewed before release.

## Responsive and compatibility acceptance criteria

- No page-level horizontal overflow occurs from `320px` through `4K`, except inside explicitly approved scroll containers.
- All essential content and actions remain available at every supported viewport width.
- No text, control, chart, tooltip, menu, dialog, badge, or table cell is unintentionally clipped or overlapped.
- Breakpoint changes can be made through the centralized breakpoint partial without editing component files.
- The compiled CSS contains the prefixes and fallbacks required by the declared browser matrix.
- Current Chrome, Edge, Firefox, and Safari pass visual, keyboard, interaction, and responsive tests.
- IE11, when included in the release target, passes the documented core-functionality and graceful-degradation test suite.
- Visual regression coverage includes at minimum `320`, `360`, `480`, `768`, `1024`, `1280`, `1440`, `1920`, `2560`, and `3840px` widths, plus component-specific boundary widths.
- A page cannot be marked complete when it only looks correct at desktop, tablet, and one mobile screenshot; continuous-width behavior and edge cases must also pass.

# Implementation order

## 1 — Freeze the visual contract

`Analyze` → `Screener` → `Portfolio` → `Factor Lab`

Confirm page hierarchy, spacing, typography, colors, navigation, tables, charts, responsive behavior, and light/dark parity.

Do not replace production pages during this step.

## 2 — Map the design to the shared UI foundation

`ISSUE_075` → shared tokens → shared layouts → shared components

Create reusable primitives for:

- Application shell and navigation
- Cards and section containers
- Metrics and score indicators
- Tables and responsive list views
- Charts and chart containers
- Filters, selectors, sliders, and buttons
- Badges, warnings, provenance, and freshness indicators

No page-specific duplicate components.

## 3 — Build shared interaction states

`ISSUE_068` + `ISSUE_069`

Implement:

- Immediate feedback for fast actions
- Skeletons and progress states for longer work
- Section-level loading and retry
- Empty, disabled, selected, hover, pressed, and keyboard-focus states
- Stale-data and degraded-mode indicators

## 4 — Implement Screener

Use Screener first to validate the application shell, filters, table density, pagination, saved screens, responsive tables, and mobile list conversion.

Keep the old Screener available behind the rollout flag until acceptance tests pass.

## 5 — Implement Analyze

`ISSUE_070` + `ISSUE_073`

Implement the new information hierarchy, score explanation, financial strengths and weaknesses, valuation charts, model provenance, data freshness, and confidence treatment.

A failed chart or model section must not prevent the rest of the page from loading.

## 6 — Implement Portfolio

Implement summary metrics, allocation, holdings, Monte Carlo results, weak-link analysis, comparison views, and section-level failure handling.

Portfolio calculations and visual presentation must remain separate.

## 7 — Implement Factor Lab

Implement centralized weight controls, total-weight validation, presets, saved configurations, backtest execution, comparison results, and subscription gating.

The UI must use the same shared controls and state components as the rest of the product.

## 8 — Responsive and accessibility pass

`ISSUE_071` + `ISSUE_072`

- Desktop: persistent navigation rail and dense research canvas
- Tablet: compact navigation and adaptive two-column layouts
- Mobile: bottom navigation, stacked cards, touch-safe controls, and condensed data views
- Meet WCAG 2.2 AA requirements

## 9 — Performance and visual validation

`ISSUE_074`

Add:

- Visual regression tests
- Responsive screenshot tests
- Accessibility tests
- Page and component performance budgets
- Interaction telemetry
- Dark/light parity checks

## 10 — Controlled rollout

- Release the redesign behind a feature flag
- Run old and new layouts in parallel
- Enable internal users first
- Migrate one page at a time
- Keep rollback available
- Remove the old layout only after production validation

# Completion rule

A page is not complete until all of the following exist:

`Desktop` + `Tablet` + `Mobile` + `Light` + `Dark` + `Loading` + `Empty` + `Error` + `Stale` + `Partial failure` + `Keyboard access`

# Initial page sequence

`Shared design engine` → `Screener` → `Analyze` → `Portfolio` → `Factor Lab` → `Settings and billing` → `Authentication` → `Landing page` → `Print and PDF views`

## Mandatory SCSS nesting structure

SCSS must mirror the logical DOM and component hierarchy so related styles remain grouped and readable.

Required pattern:

```scss
.parentDiv {
	.child {
		p {
			@include mobile {
				// responsive adjustments
			}
		}
	}
}
```

Hard constraints:

- Nest selectors in the same logical order as the component markup: parent → child → element.
- Responsive rules must live inside the selector they affect rather than in a separate bottom-of-file media-query section.
- Media-query mixins must be placed after the base declarations inside that selector.
- Use component classes for the main structure; element selectors such as `p`, `h4`, `button`, or `span` may be nested only within the owning component.
- A component must not style unrelated elements outside its own subtree.
- Avoid duplicated flat selectors when the relationship is hierarchical.
- Keep nesting intentional and readable; maximum depth is normally four levels unless deeper nesting is required by the actual component structure and is documented.
- Do not use nesting merely to increase specificity.
- All media queries must still use the centralized breakpoint mixins. Raw `@media` declarations remain prohibited.
- Stylelint or an equivalent CI check must reject violations of the approved nesting, specificity, and media-query rules.

The purpose of this structure is to make each SCSS file read like the component tree and ensure all base, child, element, and responsive rules for a component are maintained together.