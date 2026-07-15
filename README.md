# Options Signal Research

Branch: `option-chain`

Status: internal research branch. Do not publish or merge into a release branch
until the production options data source, entitlement checks, and validation
workflow are approved.

## Scope

This branch adds a provider-normalized option-chain layer, pricing helpers,
strategy analytics, and directional options signals while retaining the shared
application platform from `main`.

- Provider-neutral normalization: `codes/data/options_chain.py`
- Finnhub adapter and cache integration: `codes/data/api_fetcher.py`
- Black-Scholes-Merton pricing and Greeks: `codes/models/options_pricing.py`
- Strategy construction and ranking: `codes/models/options_strategy.py`
- Directional signal engine: `codes/models/options_signal_engine.py`

## Safety Boundary

The branch fails closed when chain data is missing, stale, unentitled, or
malformed. Signals model short-horizon mark-to-market behavior; they do not
promise expiry outcomes or present modeled values as exchange facts.

This branch is not ready for public release:

- A licensed production options source is not yet approved.
- Deployed entitlement behavior and provider quotas are not validated.
- US equity options may be American-style while pricing uses a European BSM
  approximation.
- Product wording, redistribution rights, and legal usage require approval.

## Validation

```bash
PYTHONPATH=. pytest -q \
  tests/test_options_chain_provider.py \
  tests/test_options_pricing.py \
  tests/test_options_signal_engine.py \
  tests/test_regime.py
```

Shared setup, deployment, security, and production-proof contracts are inherited
from `main`. Keep this branch synchronized by merging `main`; do not rebase the
published branch.
