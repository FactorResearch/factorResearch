# Cenvarn — Scoring Methodology

> **Transparent. Auditable. Deterministic. No Black Boxes.**

Every score produced by Cenvarn can be traced back to publicly available financial data and a documented mathematical formula.

Unlike many investment platforms, Cenvarn does not generate proprietary "AI scores" that cannot be explained. Every model is deterministic: given the same financial statements and market data, the same inputs will always produce the same result.

Our objective is not to predict the future with hidden algorithms. Instead, we combine decades of proven quantitative investing research into a transparent framework that helps investors evaluate companies consistently.

---

# Philosophy

Cenvarn is built on four core principles.

### Transparency

Every score, rating, and recommendation can be explained.

Every calculation is documented on this page, including formulas, assumptions, weighting, normalization, and interpretation.

Nothing is hidden behind proprietary black-box models.

---

### Reproducibility

Any investor should be able to reproduce our results independently.

If you download the same SEC filings and apply the formulas documented here, your results should match the scores displayed within the platform (subject only to normal market price changes).

Reproducibility is treated as a design requirement, not a marketing feature.

---

### Independence

Our scoring models are built primarily from company fundamentals rather than opinions.

We do not rely on analyst ratings to determine whether a company is attractive.

The majority of our models use objective financial information reported directly by the company.

Where external market data is required (such as price history), it is used only to calculate clearly documented metrics such as momentum or risk.

---

### Evidence-Based Investing

Every scoring model included in Cenvarn is based on an established investment framework, academic research paper, or historically validated quantitative methodology.

Examples include:

* Benjamin Graham
* Warren Buffett
* Joseph Piotroski
* Edward Altman
* Joel Greenblatt
* Robert Novy-Marx
* Modern portfolio and risk theory

Where appropriate, the original research or source material is referenced throughout this document.

---

# Data Sources

Cenvarn intentionally minimizes third-party dependencies.

### Fundamental Financial Data

All financial statement data is sourced directly from the SEC EDGAR XBRL filing system.

This includes:

* Income Statements
* Balance Sheets
* Cash Flow Statements
* Shares Outstanding
* Filing Dates
* XBRL Facts

Because the data comes directly from company filings, every calculation can be independently verified.

---

### Market Data

Market data is retrieved from multiple providers in priority order:

1. Finnhub
2. Tiingo
3. Alpha Vantage

This redundancy improves reliability while ensuring calculations remain deterministic.

---

### What We Do Not Use

To keep scoring transparent and reproducible, Cenvarn does **not** use:

* Black-box AI scoring
* Undocumented proprietary formulas
* Paid analyst opinions as part of the composite score
* Hidden weighting adjustments
* Manual overrides

Every point awarded by every model is earned through documented rules.

---

# How to Read This Document

This methodology is intended for users who want to understand exactly how Cenvarn evaluates companies.

Each model follows the same structure:

* Purpose
* Data Required
* Scoring Criteria
* Mathematical Formula
* Interpretation
* Limitations

You do not need to understand every formula to use the platform.

The application performs every calculation automatically.

This document exists so that every result can be independently verified by anyone who wishes to inspect the methodology.

---

# Table of Contents

The remainder of this document contains the complete implementation details for every scoring model used by Cenvarn, including:

* Composite Score
* Graham Model
* Buffett Model
* Piotroski F-Score
* Altman Z-Score
* Quality
* Momentum
* Risk Metrics
* Profitability
* Free Cash Flow Quality
* Capital Allocation
* Growth Quality
* Earnings Revision
* Factor Momentum
* Greenblatt Magic Formula
* Regime Overlay
* Insider Activity
* Alternative Data
* Data Lineage
* Reproducibility

---

*Every formula documented below reflects the implementation currently used within the platform. As the platform evolves, this document is updated alongside the codebase to ensure users always have an accurate and complete description of how scores are calculated.*
