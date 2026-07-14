# V0.5 Architecture Freeze

This phase is internal-only. It adds shared architecture primitives that future
engines can adopt without changing user-facing pages.

## Engine Contract

Each analysis engine should expose an `EngineContract` with:

- input schema
- output schema
- validation behavior
- feature flags
- documentation
- interpretation guide

Feature flags are:

- `internal`
- `beta`
- `v1`
- `v2`
- `enterprise`

## Shared Math

Financial calculations should use `codes.core.financial_math` where practical.
The module operates on normalized numeric sequences and does not call providers.

Included primitives:

- CAGR
- volatility
- Sharpe
- Sortino
- Calmar
- alpha
- beta
- correlation
- covariance
- regression
- drawdown
- percentile normalization
- winsorization
- ranking

## Provider Boundary

Business logic must not call vendor APIs directly. Provider adapters should
return canonical objects from `codes.data.providers` before analysis engines run.

## Interpretation Guide

Contracts should describe how outputs are meant to be read. This prevents
internal scores from being treated as direct investment instructions and keeps
future Website, API, Desktop, and Mobile surfaces aligned.
