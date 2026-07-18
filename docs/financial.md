# Purpose
Guarantee consistent, reproducible, explainable, and point-in-time-correct financial calculations across every model and product surface.
# Formula contract
Every material calculation must define:
- Formula name and version.
- Mathematical expression.
- Input definitions, source, units, currency, date basis, and adjustment status.
- Missing, negative, zero, stale, anomalous, and restated-data treatment.
- Precision and rounding policy.
- Output range, units, and interpretation.
- Whether output is authoritative, estimated, normalized, or display-only.
# Numerical rules
- Use decimal-safe arithmetic for money and defined precision for ratios.
- Do not round intermediate values unless methodology requires it.
- Rounding for storage, comparison, and display must be separately defined.
- Currency conversion must record source rate, rate timestamp, source currency, target currency, and conversion policy.
# Historical correctness
- Prevent look-ahead bias.
- Use information available as of the analysis date.
- Preserve filing dates, effective dates, restatements, and model versions.
- Document survivorship-bias limitations.
- Adjust prices and shares consistently for splits and corporate actions.
# Reproducibility
Every stored analysis must identify model version, data snapshot or lineage, execution date, assumptions, and configuration.
# Validation
Use known-answer tests, independent reconciliation, boundary tests, and regression fixtures for every model.
# AI implementation requirements
The AI must never invent financial assumptions silently. Ambiguity must be represented explicitly in code, metadata, tests, and user-facing warnings.
