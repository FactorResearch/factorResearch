# Design-system review checklist

Use this checklist for every production UI change. A one-off component needs an
explicit design-system review; copying an existing page-specific pattern is not
approval.

- [ ] Existing semantic tokens cover the intent. If not, add and generate one token rather than a raw color, radius, layer, spacing, or motion value.
- [ ] Existing primitives and layouts were used for buttons, links, loading, alerts, errors, cards, tables, tabs, forms, overlays, and notifications.
- [ ] A genuinely reusable missing behavior was added to the central primitive, not to one page.
- [ ] Default, hover, focus-visible, active, selected, disabled, loading, success, warning, error, and read-only behavior was considered where applicable.
- [ ] Keyboard order, visible focus, accessible name, status semantics, Escape, focus return, focus trap, and scroll lock were tested where applicable.
- [ ] Touch targets remain at least the shared minimum and essential information is not hover-only.
- [ ] Dark/light, reduced-motion, high-contrast, mobile, desktop, 200% zoom, and long localized text were checked.
- [ ] Financial meaning uses a word, value, icon, or shape in addition to color and distinguishes zero, unavailable, stale, partial, and not applicable.
- [ ] Destructive confirmation is proportional to impact; reversible low-risk actions prefer local undo.
- [ ] Loading and delayed content reserve stable space and preserve valid prior content.
- [ ] Catalogue examples, contract tests, and intentional visual baselines were updated.
- [ ] `./scripts/release-gate.sh` and the browser design-system audit pass.

The release gate rejects direct production construction of `html.Button`,
`dcc.Link`, and `dcc.Loading`, raw design values, unmanaged radii, and unmanaged
z-index values. Additions should flow through
`codes.app_modules.design_system`; exceptions require a documented review and a
narrow, registered compatibility reason.
