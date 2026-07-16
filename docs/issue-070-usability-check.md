# ISSUE_070 hierarchy usability check

The Analyze and Portfolio first views use the same five-second comprehension contract:

1. State the primary conclusion or portfolio health before detailed evidence.
2. Name the strongest driver and weakest factor without requiring a disclosure to open.
3. Keep critical risk and research freshness visible.
4. Put formulas, raw inputs, history, charts, and simulation after those conclusions.
5. Link Portfolio warnings directly to the affected holding.

The automated contract in `tests/test_issue_070_progressive_disclosure.py` verifies the reading order, factor ranking, warning visibility, drilldown targets, and session/back-forward restoration. The responsive contract keeps the section index horizontally reachable on small screens and collapses all summary grids to a single column.

For a moderated check, show Analyze for five seconds and ask: “What is the conclusion, and what is the weakest factor?” Then show Portfolio and ask: “Which holding should you inspect first, and why?” A pass requires both answers without prompting or opening an advanced disclosure.
