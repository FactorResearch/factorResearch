# Options Signal Research

Branch: `option-chain`

Status: internal research branch. Do not publish or merge into a release branch until the production options data source, entitlement checks, and validation workflow are approved.

## What this branch does

This branch builds the options-analysis foundation for the app. It adds a provider-normalized option-chain layer, pricing helpers, options strategy analytics, and analysis-pipeline wiring so the rest of the engine can consume one stable contract shape instead of vendor-specific payloads.

Implemented work in this branch:

- Provider-neutral option-chain normalization in [codes/data/options_chain.py](/home/amin/Downloads/graham-app/codes/data/options_chain.py)
- Finnhub option-chain adapter and cache integration through [codes/data/api_fetcher.py](/home/amin/Downloads/graham-app/codes/data/api_fetcher.py)
- Black-Scholes-Merton pricing, Greeks, expected payoff, and probability helpers in [codes/models/options_pricing.py](/home/amin/Downloads/graham-app/codes/models/options_pricing.py)
- Strategy candidate construction and ranking in [codes/models/options_strategy.py](/home/amin/Downloads/graham-app/codes/models/options_strategy.py)
- Directional options signal engine in [codes/models/options_signal_engine.py](/home/amin/Downloads/graham-app/codes/models/options_signal_engine.py)
- Analysis integration so normalized chain data reaches the options model without leaking provider-specific fields

## What users should expect

The branch is designed to fail closed instead of inventing data. If live chain data is missing, stale, unentitled, or malformed, the engine degrades to a stable unavailable or stale response and avoids presenting fake contract analysis.

The signal engine models short-horizon mark-to-market behavior. It does not promise expiry outcomes and it does not pretend exchange-theoretical values and model-theoretical values are the same thing.

## Data and licensing boundaries

This branch is not ready for public release on data grounds alone.

- The implemented live adapter is Finnhub-based
- Production release still requires confirmed paid options-chain entitlement and permitted product usage
- US equity options are commonly American-style, while the pricing model here is a Black-Scholes-Merton European approximation
- The branch should be treated as research infrastructure until the provider, latency, refresh rules, and legal usage are signed off

## What this branch does not claim

- No claim of institution-grade options execution support
- No order-routing or broker integration
- No volatility-surface calibration
- No historical implied-volatility warehouse
- No premium chain redistribution rights

## Tests tied to this branch

The branch already has focused coverage for the implemented surface:

- [tests/test_options_chain_provider.py](/home/amin/Downloads/graham-app/tests/test_options_chain_provider.py)
- [tests/test_options_pricing.py](/home/amin/Downloads/graham-app/tests/test_options_pricing.py)
- [tests/test_options_signal_engine.py](/home/amin/Downloads/graham-app/tests/test_options_signal_engine.py)
- [tests/test_regime.py](/home/amin/Downloads/graham-app/tests/test_regime.py)

## Local use

Regular app startup still applies. This branch does not require a separate JSON dataset and does not introduce a new market database.

If you want to inspect the options research surface directly, start with:

1. `codes/data/options_chain.py`
2. `codes/models/options_pricing.py`
3. `codes/models/options_signal_engine.py`
4. `tests/test_options_chain_provider.py`

## Release position

Keep this branch isolated until all of the following are true:

- licensed production options data source is selected
- entitlement behavior is validated in the deployed environment
- product wording is reviewed so modeled analytics are not presented as raw exchange facts
- portfolio and analysis UI expose the feature in a way that matches the paid-data constraints
