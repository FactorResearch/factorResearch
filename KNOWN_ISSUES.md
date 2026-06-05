# KNOWN_ISSUES.md

# Financial Model Audit Backlog

Purpose:
Track known mathematical, financial-model, and implementation issues discovered during code review.

Status values:

* [ ] Open
* [~] In Progress
* [x] Completed
* [?] Requires Investigation

---
# ISSUE-001

Status: []

Title:
Division by zero in greenblatt.py

Priority:
Critical

File:
greenblatt.py

Problem:
we are dividing by zero

Required Fix:
fix the bug 




Acceptance Criteria:

* Division by zero is no longer there
* fixed code is pushed to git



# Future Audit Candidates

Status: [?]

Potential Review Areas:

* Enterprise value calculations
* FCF yield calculations
* Share dilution handling
* CAGR calculations
* Earnings normalization
* Monte Carlo return assumptions
* Drawdown calculations
* Correlation estimation methodology
* Data survivorship bias
* Missing financial statement handling

---

# Unit Test Coverage Backlog

Purpose:
Track missing unit test coverage per module.
All test files live in tests/ at the repository root.
Use pytest. No test should hit the network or disk — mock all I/O.

Existing partial coverage:
* tests/test_graham_consecutive_dividends.py  — graham.py (ISSUE-002 only)
* tests/test_risk_metrics_sortino.py          — risk_metrics.py (ISSUE-001 only)
* tests/test_issue008_greenblatt_composite.py — greenblatt.py (ISSUE-008 only)
* test_issue001_div_lookback.py               — sec_data.py (ISSUE-009 only)

---

## TEST-005

Status: [ ]

Title:
Full Unit Tests for piotroski.py

File:
tests/test_piotroski.py

Required Tests:

* all_pass: sec dict where all 9 signals fire → f_score=9, label="strong"
* all_fail: sec dict where no signal fires → f_score=0, label="weak"
* neutral_range: exactly 5 signals fire → label="neutral"
* f1_roa_positive: net_inc > 0, total_assets > 0 → F1=1
* f1_roa_negative: net_inc < 0 → F1=0
* f2_ocf_positive: op_cf > 0 → F2=1
* f2_ocf_negative: op_cf < 0 → F2=0
* f3_roa_improving: roa this year > roa prior year → F3=1
* f3_roa_declining: roa this year < roa prior year → F3=0
* f4_accruals_pass: ocf/assets > roa → F4=1
* f4_accruals_fail: ocf/assets <= roa → F4=0
* f5_leverage_primary: lt_debt present, ratio falling → F5=1
* f5_leverage_fallback: lt_debt missing, tot_lib present → uses TotalLiab/Assets, still scores
* f5_leverage_missing: both lt_debt and tot_lib absent → F5=0, no crash
* f6_current_ratio_improving: cr this year > cr prior year → F6=1
* f7_no_dilution_within_tolerance: shares up 0.5% → F7=1
* f7_dilution_detected: shares up 2% → F7=0
* f8_gross_margin_improving: gm this year > gm prior year → F8=1
* f9_asset_turnover_improving: at this year > at prior year → F9=1
* missing_prior_year: only one year of data → F3, F5, F6, F8, F9 all score 0, no crash
* missing_all_data: empty sec dict → f_score=0, all signals score 0, no crash

Acceptance Criteria:

* No network or file I/O.
* Every signal (F1–F9) has a pass case and a fail case.
* Fallback and missing-data paths explicitly tested.

---

## TEST-006

Status: [ ]

Title:
Full Unit Tests for graham.py

File:
tests/test_graham.py

Note:
tests/test_graham_consecutive_dividends.py covers ISSUE-002 only.
This test file must cover the full module.

Required Tests:

* grade_A: total_score >= 70 → grade="A", grade_label="Defensive"
* grade_B: total_score 50-69 → grade="B", grade_label="Enterprising"
* grade_C: total_score 30-49 → grade="C", grade_label="Speculative"
* grade_D: total_score < 30 → grade="D", grade_label="Avoid"
* pe_at_ceiling: P/E = 15.0 → pe_score=15
* pe_above_ceiling: P/E > 20 → pe_score=0
* pe_negative_earnings: eps < 0 → pe_score=0
* pe_no_price: price=None → pe=None, pe_score=0
* pb_deep_value: P/B <= 1.5 → pb_score=10
* pb_expensive: P/B > 2.5 → pb_score=0
* gn_full_margin: price <= 67% of Graham Number → gn_score=20
* gn_partial_margin: 67% < price <= GN → gn_score=10
* gn_no_margin: price > Graham Number → gn_score=0
* gn_no_price: price=None → gn_score=0
* consecutive_dividends_gap: gap in div_hist → div_years stops at gap
* consecutive_dividends_continuous: uninterrupted 20+ years → dv_score=10
* consecutive_dividends_empty: no div_hist entries → div_years=0, dv_score=0
* eps_loss_year: any eps value < 0 in history → eps_score=0 regardless of growth
* eps_insufficient_history: fewer than 5 years → eps_score=0
* nnwc_net_net: nnwc > mkt_cap → nn_score=5
* nnwc_not_net_net: nnwc < mkt_cap → nn_score=0
* total_score_bounded: total_score always in [0, 100]

Acceptance Criteria:

* No network or file I/O.
* consecutive_dividends_gap is a dedicated failing test that passes only after ISSUE-002 fix.
* Every scoring criterion has at least one pass and one fail case.

---

## TEST-007

Status: [ ]

Title:
Full Unit Tests for portfolio.py (pure functions only)

File:
tests/test_portfolio.py

Required Tests:

* split_factor_no_splits: empty splits list → factor=1.0
* split_factor_one_split_before: one 2:1 split on date <= as_of → factor=2.0
* split_factor_one_split_after: split date > as_of → factor=1.0 (not counted)
* split_factor_cumulative: two splits both before as_of → factors multiplied
* add_holding_success: valid symbol, shares, price → holding added, error=""
* add_holding_max_cap: portfolio already at MAX_HOLDINGS → error string returned
* add_holding_min_shares: shares < MIN_SHARES → error string returned
* add_holding_duplicate: same symbol twice → error string returned
* remove_holding_present: symbol in portfolio → removed, error=""
* remove_holding_missing: symbol not in portfolio → error string returned
* montecarlo_geometric_drift: drift used in simulation is μ - σ²/2, not μ (ISSUE-004)
* port_variance_uses_covariance: σp = sqrt(wᵀΣw), not sum of weighted stds (ISSUE-003)
* run_montecarlo_returns_bands: p10 <= p50 <= p90 at every time step
* run_montecarlo_start_value: paths[:,0] == start_value for all simulated paths

Acceptance Criteria:

* No network or file I/O. Mock alpha_vantage_client and cache entirely.
* montecarlo_geometric_drift and port_variance_uses_covariance are dedicated failing tests
  that pass only after ISSUE-004 and ISSUE-003 fixes respectively.
* Storage helpers (save/load/delete/list) tested with a mocked cache module.

---

## Test Infrastructure Notes

* Test runner: pytest
* Run all tests with: pytest tests/ -q
* Mock all external calls with unittest.mock.patch or pytest-mock
* Shared sec_facts fixture builders belong in tests/conftest.py
* Do not import app.py in any unit test (pulls in Dash and all dependencies)
* Each test file is self-contained — no shared mutable state across files
* Tests for known-open issues should be marked @pytest.mark.xfail(strict=True)
  so they fail visibly until the issue is resolved, then automatically pass

---

# AI Agent Instructions

When working on an issue:

1. Read AI_CONTEXT.md.
2. Read PROJECT_MAP.md.
3. Read this file.
4. Work on only one issue at a time.
5. Verify issue exists before implementing.
6. Produce minimal diffs.
7. Add tests.
8. Update issue status after completion.

Do not refactor unrelated code.
Do not scan the entire repository unless explicitly requested.
