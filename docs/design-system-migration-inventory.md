# Design-system migration inventory

| Area | Current state | Replacement | Priority | Exception owner and removal trigger |
|---|---|---|---|---|
| Analyze overview and sections | Reference migration complete | Typed section definitions, container, analysis grid | Complete | None |
| Portfolio summary, state, return, actions, holdings table | Reference migration complete | Financial metrics/delta, empty state, dashboard grid, responsive table | Complete | None |
| App shell and profile theme | Semantic theme bridge complete; legacy classes remain | Layout and theme tokens | High | Frontend; remove legacy shell values when shell is migrated |
| Screener table and quick peek | Legacy component CSS | Responsive table, drawer, metric and state primitives | High | Frontend; ISSUE_072 implementation |
| Analyze legacy scorecards | Shared legacy helper, token adoption partial | Card, score, verdict and metric primitives | High | Frontend; when each model card receives contract tests |
| Portfolio simulation/comparison | Legacy scorecards and Plotly wrappers | Chart shell and analysis-section state | High | Frontend; ISSUE_068/072 implementation |
| Factor Lab | Page-specific controls and cards | Form fields, grid, chart shell | Medium | Frontend; next Factor Lab workflow change |
| Pricing/profile/supporting screens | Legacy shared classes | Page header, card, form, alert and layout primitives | Medium | Frontend; ISSUE_069 migration phase |
| Plotly chart colors and dimensions | Necessary library-specific configuration | Semantic chart adapter | Medium | Frontend; ISSUE_072 adds centralized chart theme |
| Legacy SCSS partials | 29 partials with historical raw values | Generated tokens plus `_design_system.scss` | Incremental | Frontend; delete a partial only after all selectors have zero references |

No active ISSUE_076 architecture exception is introduced. The inventory is a migration queue, not permission to add new bypasses. `scripts/check-design-system.py` blocks new raw colors, radii, and z-index values unless a documented technical exception is attached.
