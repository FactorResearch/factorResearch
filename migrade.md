# SCSS Color Architecture Cleanup and Palette Migration

Work on branch:

```text
ui/mockup-parity
```

## Objective

Clean up the entire color architecture and migrate the application to the approved black/green Cenvarn palette.

The final system must have:

* One handwritten SCSS file containing all color values.
* SCSS variables only for colors.
* No color-related CSS custom properties.
* No `var(--color-...)`.
* No `var(--cv-...)`.
* No color-related `var(--fr-...)`.
* No hard-coded hex, RGB, HSL, or named color values outside the canonical color file.
* No duplicate color partials.
* No undefined Sass namespaces.
* No automated global replacement that changes files without understanding their imports and variable roles.

Do not use or modify the previous migration Bash scripts. Perform the migration directly and carefully.

---

# 1. Preserve the Current Worktree

Before changing anything:

```bash
git status --short
git diff
git branch --show-current
```

Do not run `git reset --hard`.

Do not remove unrelated work.

Identify and remove only artifacts created by the failed color-migration attempts, after confirming they are not part of valid user work.

Likely failed-migration artifacts include:

```text
assets/style/foundation/_colors.scss
assets/style.dark.scss
assets/style.light.scss
assets/style.dark.css
assets/style.light.css
scripts/consolidate-colors.sh
scripts/consolidate-colors-v2.sh
scripts/repair-color-consolidation.sh
scripts/convert-colors-to-scss-only.sh
```

Do not delete any file merely because it appears in this list. Inspect Git history and the current diff first.

---

# 2. Inventory the Existing System

Before editing, produce an inventory of:

1. Every SCSS file defining a color.
2. Every SCSS file importing a color or token module.
3. Every Sass color variable reference.
4. Every color-related CSS custom property.
5. Every hard-coded color.
6. Every stylesheet entrypoint.
7. Every compiled CSS file loaded by Dash.
8. Every Python or JavaScript file containing duplicated UI color values.

Run searches equivalent to:

```bash
rg -n \
  --glob '*.scss' \
  --glob '*.css' \
  --glob '*.py' \
  --glob '*.js' \
  '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|hsl\(|hsla\(|var\(--|@use|@forward|@import' \
  assets codes scripts tests
```

Also inspect:

```text
assets/_colors.scss
assets/_landing_tokens.scss
assets/legal_pages.scss
assets/landing_pre.scss
assets/style.scss
assets/style/_tokens.scss
assets/style/_design_tokens.generated.scss
assets/style/_design_system.scss
assets/style/_app-shell.scss
assets/style/_base.scss
assets/style/_screener.scss
assets/style/_mockup-shell.scss
assets/style/_analysis-mockup.scss
assets/style/_factor-hexagon.scss
assets/style/foundation/_index.scss
assets/style/foundation/_mixins.scss
codes/app_modules/design_system/tokens.py
scripts/generate-design-tokens.py
package.json
```

Do not begin deletion until this inventory is complete.

---

# 3. Target Architecture

Use this as the only canonical color file:

```text
assets/_colors.scss
```

This location is intentional. It is accessible to:

* Root-level entrypoints such as `assets/legal_pages.scss`.
* Root-level landing-page files.
* Partials inside `assets/style/`.
* Sass compilation using `--load-path=assets`.

Every SCSS file must import it consistently as:

```scss
@use "colors" as c;
```

Compile Sass with:

```bash
--load-path=assets
```

Do not use inconsistent paths such as:

```scss
@use "../colors" as c;
@use "foundation/colors" as cv;
@use "colors" as cv;
```

The canonical namespace across the repository must be:

```scss
c
```

Therefore, feature code should look like:

```scss
@use "colors" as c;

.card {
  background: c.$surface-raised;
  color: c.$text-primary;
  border-color: c.$border-default;
}
```

---

# 4. Canonical Palette

Replace the contents of `assets/_colors.scss` with a structured SCSS-only theme system.

It must contain:

## Raw palette

```scss
$black: #090d0b;
$black-soft: #101612;
$black-raised: #141c17;
$black-overlay: #1a241e;

$white: #ffffff;
$off-white: #f5f7f8;
$off-white-soft: #f8faf9;
$off-white-muted: #eef3f0;

$green-400: #55ce8a;
$green-500: #39b873;
$green-700: #16834c;
$green-800: #0e683b;
$green-dark-soft: #12291d;
$green-light-soft: #e7f5ed;

$gray-100: #edf4ef;
$gray-300: #cbd7cf;
$gray-400: #91a097;
$gray-500: #68756d;
$gray-600: #526057;
$gray-700: #34433a;
$gray-800: #253229;
$gray-900: #152019;

$red-400: #ef6b70;
$red-700: #c33d42;
$red-dark-soft: #32191b;
$red-light-soft: #fae9ea;

$yellow-400: #e8af45;
$yellow-700: #b77910;
$yellow-dark-soft: #332713;
$yellow-light-soft: #fff3d8;

$blue-500: #2f66dd;
$green-chart: #2cbc55;
$yellow-chart: #d8a322;
$purple-500: #8739c9;
```

## Configurable theme

Use a configurable variable:

```scss
$theme: dark !default;
```

Use Sass maps and `sass:map`, not long chains of deprecated `if()` calls.

Define light and dark semantic maps:

```scss
$dark-theme: (
  surface-canvas: $black,
  surface-base: $black-soft,
  surface-raised: $black-raised,
  surface-overlay: $black-overlay,
  text-primary: $gray-100,
  text-muted: $gray-400,
  text-subtle: $gray-500,
  border-default: $gray-800,
  border-strong: $gray-700,
  action-primary: $green-500,
  action-primary-hover: $green-400,
  action-primary-soft: $green-dark-soft,
  status-positive: $green-500,
  status-positive-soft: $green-dark-soft,
  status-warning: $yellow-400,
  status-warning-soft: $yellow-dark-soft,
  status-danger: $red-400,
  status-danger-soft: $red-dark-soft,
  status-info: $blue-500
);

$light-theme: (
  surface-canvas: $off-white,
  surface-base: $white,
  surface-raised: $off-white-soft,
  surface-overlay: $off-white-muted,
  text-primary: $gray-900,
  text-muted: $gray-500,
  text-subtle: $gray-600,
  border-default: #dce5df,
  border-strong: $gray-300,
  action-primary: $green-700,
  action-primary-hover: $green-800,
  action-primary-soft: $green-light-soft,
  status-positive: $green-700,
  status-positive-soft: $green-light-soft,
  status-warning: $yellow-700,
  status-warning-soft: $yellow-light-soft,
  status-danger: $red-700,
  status-danger-soft: $red-light-soft,
  status-info: $blue-500
);
```

Create a private active-theme map and expose semantic Sass variables:

```scss
$active-theme: if($theme == light, $light-theme, $dark-theme);

$surface-canvas: map.get($active-theme, surface-canvas);
$surface-base: map.get($active-theme, surface-base);
$surface-raised: map.get($active-theme, surface-raised);
$surface-overlay: map.get($active-theme, surface-overlay);

$text-primary: map.get($active-theme, text-primary);
$text-muted: map.get($active-theme, text-muted);
$text-subtle: map.get($active-theme, text-subtle);

$border-default: map.get($active-theme, border-default);
$border-strong: map.get($active-theme, border-strong);

$action-primary: map.get($active-theme, action-primary);
$action-primary-hover: map.get($active-theme, action-primary-hover);
$action-primary-soft: map.get($active-theme, action-primary-soft);

$status-positive: map.get($active-theme, status-positive);
$status-positive-soft: map.get($active-theme, status-positive-soft);
$status-warning: map.get($active-theme, status-warning);
$status-warning-soft: map.get($active-theme, status-warning-soft);
$status-danger: map.get($active-theme, status-danger);
$status-danger-soft: map.get($active-theme, status-danger-soft);
$status-info: map.get($active-theme, status-info);

$chart-1: $blue-500;
$chart-2: $green-chart;
$chart-3: $yellow-chart;
$chart-4: $purple-500;
$chart-5: $status-danger;
```

Legacy aliases may exist temporarily inside this file only, but they must be removed before the task is considered complete.

---

# 5. Fix Sass Entry Points

The first statement in the dark application entrypoint must configure the color module:

```scss
@use "colors" with (
  $theme: dark
);
```

Then load the application partials.

The dark application build must compile into:

```text
assets/style.css
```

This is the file the current Dash application already loads.

Create a light entrypoint outside the automatic application stylesheet sequence:

```text
scss-entrypoints/style.light.scss
```

Its first statement must be:

```scss
@use "colors" with (
  $theme: light
);
```

Compile it outside the Dash auto-loaded assets directory, for example:

```text
build/themes/style.light.css
```

Do not place both `style.dark.css` and `style.light.css` inside `assets/` unless the application explicitly prevents Dash from automatically loading both.

Inspect the existing theme-toggle implementation. Preserve light/dark switching by explicitly swapping the loaded stylesheet rather than relying on color CSS custom properties.

Do not break the current default dark application while implementing light mode.

---

# 6. Migrate `_tokens.scss`

`assets/style/_tokens.scss` must no longer define its own color palette.

Remove color definitions such as:

```scss
$bg
$surface
$surface-soft
$card
$card-raised
$border
$text
$blue
$cyan
$green
$red
$amber
$light-bg
$light-surface
$light-card
```

Remove all color-related declarations such as:

```scss
--fr-bg
--fr-surface
--fr-card
--fr-border
--fr-text
--fr-accent
--fr-positive
--fr-warning
--fr-danger
```

Do not replace those with another CSS custom-property namespace.

Keep `_tokens.scss` only for non-color values such as:

* Typography
* Font sizes
* Spacing
* Radii
* Z-index
* Motion
* Non-color layout measurements

Where shadows require colors, consume the canonical module:

```scss
@use "colors" as c;

$shadow-sm: 0 8px 20px rgba(c.$surface-canvas, 0.18);
```

---

# 7. Migrate Every Feature Partial

Migrate feature files one at a time.

Do not run a blind repository-wide regex replacement.

For each file:

1. Add:

   ```scss
   @use "colors" as c;
   ```

2. Replace hard-coded colors with semantic variables.

3. Replace old `c.$ink-*`, `c.$cenvarn-*`, and other identity variables with semantic variables.

4. Replace color CSS custom properties with SCSS variables.

5. Compile immediately after editing the file.

6. Only continue when compilation passes.

Examples:

```scss
background: var(--cv-canvas);
```

becomes:

```scss
background: c.$surface-canvas;
```

```scss
color: var(--fr-text);
```

becomes:

```scss
color: c.$text-primary;
```

```scss
border-color: #b18a54;
```

becomes:

```scss
border-color: c.$action-primary;
```

```scss
.factor-hex-label {
  fill: var(--color-legacy-9eafc7);
}
```

must become a meaningful canonical variable, for example:

```scss
.factor-hex-label {
  fill: c.$chart-label;
}
```

Add `$chart-label` to `assets/_colors.scss`.

Do not create variables such as:

```scss
$legacy-9eafc7
```

unless the exact semantic purpose cannot be determined. Review the component and assign a meaningful name.

Prioritize these files:

```text
assets/style/_base.scss
assets/style/_app-shell.scss
assets/style/_tokens.scss
assets/style/_design_system.scss
assets/style/_screener.scss
assets/style/_mockup-shell.scss
assets/style/_analysis-mockup.scss
assets/style/_factor-hexagon.scss
assets/style/_composite-trend.scss
assets/style/_compatibility.scss
assets/style/foundation/_mixins.scss
assets/_landing_tokens.scss
assets/landing_pre.scss
assets/legal_pages.scss
```

---

# 8. Embedded SVG and Data-URI Colors

Do not leave hard-coded colors inside SVG data URIs.

Preferred solutions, in order:

1. Replace the SVG with regular inline SVG using `currentColor`.
2. Use an SVG mask and set `background-color` with a canonical SCSS variable.
3. Generate the encoded SVG value using interpolation from a canonical SCSS variable.

Do not exempt data URIs from the color audit.

---

# 9. Remove Duplicate Systems

After all imports and usages are migrated, inspect whether these files still provide unique non-color functionality:

```text
assets/style/_design_tokens.generated.scss
codes/app_modules/design_system/tokens.py
scripts/generate-design-tokens.py
```

The target is:

```text
assets/_colors.scss
    All handwritten application colors.

assets/style/_tokens.scss
    Non-color design tokens only.
```

If `_design_tokens.generated.scss` duplicates `_tokens.scss`, migrate its remaining non-color tokens and delete it.

If `tokens.py` contains a color group that is not consumed by Python runtime code, remove that color group.

If Python genuinely requires colors for Plotly or server-rendered charts, generate a Python file from `assets/_colors.scss`. Do not maintain a second handwritten palette.

Any generated file must begin with:

```text
Generated from assets/_colors.scss. Do not edit manually.
```

Delete duplicate files only after:

```bash
rg -n 'filename-or-import-name' assets codes scripts tests
```

returns no remaining references.

---

# 10. Build Commands

Add predictable scripts to `package.json`.

The Sass load path must be explicit:

```json
{
  "scripts": {
    "build:styles:dark": "sass --load-path=assets --no-source-map assets/style.scss assets/style.css",
    "build:styles:light": "mkdir -p build/themes && sass --load-path=assets --no-source-map scss-entrypoints/style.light.scss build/themes/style.light.css",
    "build:styles": "npm run build:styles:dark && npm run build:styles:light",
    "watch:styles": "sass --load-path=assets --watch assets/style.scss:assets/style.css",
    "audit:colors": "python scripts/audit-scss-colors.py"
  }
}
```

Update paths if the repository already has an established build directory, but preserve the architecture.

---

# 11. Add an Enforcement Audit

Create:

```text
scripts/audit-scss-colors.py
```

The audit must fail when:

* A raw color appears outside `assets/_colors.scss`.
* A color CSS custom property is defined.
* A color CSS custom property is consumed.
* A deprecated color namespace appears.
* A feature partial imports a duplicate color module.
* A referenced Sass color variable is undefined.
* More than one handwritten SCSS file owns raw color values.

Audit these forms:

```text
#[0-9a-fA-F]{3,8}
rgb(...)
rgba(...)
hsl(...)
hsla(...)
var(--color-...)
var(--cv-...)
var(--fr-bg)
var(--fr-surface...)
var(--fr-card...)
var(--fr-border...)
var(--fr-text...)
var(--fr-accent...)
var(--fr-positive...)
var(--fr-warning...)
var(--fr-danger...)
```

Allow `rgba(c.$variable, alpha)` outside the canonical file because the actual color comes from the canonical module.

Do not ignore encoded SVG colors. Migrate them.

---

# 12. Validation

Run all of the following:

```bash
npm run audit:colors
npm run build:styles
npm run check:styles
pytest tests/test_issue_069_design_system.py
python codes/app.py
```

Also run:

```bash
rg -n \
  --glob '*.scss' \
  'var\(\s*--(color-|cv-|fr-(bg|surface|card|border|text|accent|positive|warning|danger))' \
  assets
```

Expected result:

```text
No matches.
```

Run:

```bash
rg -n \
  --glob '*.scss' \
  '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|hsl\(|hsla\(' \
  assets \
  -g '!_colors.scss'
```

Expected result:

* No raw color values.
* `rgba(c.$variable, alpha)` is acceptable.
* No other matches.

Confirm the old palette is absent from compiled application CSS:

```bash
rg -n \
  '#0e1829|#b18a54|#f3f2f1|#0f1b2d|#15243a|#4f9cf9' \
  assets/style.css
```

Expected result:

```text
No matches, except a chart color only when explicitly approved.
```

Confirm the new dark palette exists:

```bash
rg -n \
  '#090d0b|#101612|#141c17|#39b873|#55ce8a' \
  assets/style.css
```

---

# 13. Visual Acceptance

Open and inspect:

* Screener
* Analyze
* Portfolio
* Factor Lab
* Navigation rail
* Search
* Tables
* Cards
* Buttons
* Alerts
* Factor hexagon
* Charts
* Legal pages
* Landing page
* Mobile layout

Dark mode must visibly use:

* Near-black page background
* Dark charcoal surfaces
* Green primary actions
* White or pale-gray text
* Yellow warnings
* Red danger states

The application must not retain the previous navy, beige, or gold identity palette.

Verify both desktop and mobile.

---

# 14. Safety Rules

* Do not use another broad Bash migration script.
* Do not globally replace imports without compiling after each group.
* Do not delete a file before proving it has no consumers.
* Do not create a third compatibility color system.
* Do not leave temporary `legacy-*` names in the final result.
* Do not edit compiled CSS manually.
* Do not claim success based only on Sass compilation.
* Do not finish until the running Dash application visibly uses the new palette.

---

# 15. Final Report

At completion, report:

1. Canonical color file.
2. Every migrated SCSS file.
3. Every deleted duplicate file.
4. Every build-script change.
5. Every updated test.
6. Audit output.
7. Sass compilation output.
8. Test output.
9. Remaining exceptions, if any.
10. Confirmation that `python codes/app.py` visibly renders the new palette.

Do not stop after producing a plan. Implement the migration, compile it, run the application, inspect the rendered result, and correct any remaining old colors.
