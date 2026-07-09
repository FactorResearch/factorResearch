"""Dash layout composition."""

from dash import dcc, html

from codes.engine import scorer

from .config import BLUE, BORDER, CARD, MUTED, TEXT


def build_layout():
    return html.Div(className="app-container", children=[
        dcc.Location(id="url", refresh=False),
        # Header
        html.Div(className="app-header", children=[
            html.Img(src="./assets/logo.png", className="app-header-icon"),
            html.Div(className="app-header-content", children=[
           
                html.H1("FactorResearch"),
            
                html.P("Orthogonal factor score: Value, Quality, Momentum, Profitability, FCF Quality, Earnings Revisions, Capital Allocation, Growth Quality, Risk, and Altman."),
                html.P(
                    "Not financial advice. For informational purposes only. "
                    "See Terms of Service and Privacy Policy.",
                    style={"fontSize": "11px", "color": "#9e9e9e", "marginTop": "4px"}
                ),
            ])
        ]),
        # Tabs
        html.Div(className="tab-bar", children=[
            html.Button("📊 Screener",  id="tab-screener-btn",  className="tab-btn active"),
            html.Button("🔍 Analyze",   id="tab-analyze-btn",   className="tab-btn"),
            html.Button("💼 Portfolios", id="tab-portfolio-btn", className="tab-btn"),
            html.Button("🧪 Factor Lab", id="tab-factorlab-btn", className="tab-btn"),
        ]),
        # ── Tab: Screener ────────────────────────────────────────────────────────
        html.Div(id="tab-screener", className="screener-content block", children=[
            html.Div(className="screener-toolbar", children=[
                html.Div(className="screener-controls", children=[
                    html.Button(
                        "Load Universe (~10,000 U.S security)",
                        id="load-universe-btn",
                        className="load-btn",
                        n_clicks=0,
                        disabled=False
                    ),
                    html.Div(id="screener-progress-info", className="screener-info"),
                ]),
                html.Div(className="screener-controls flex gap-lg align-items-center", children=[
                    html.Label("Filter by sector:", className="text-sm text-muted"),
                    dcc.Dropdown(
                        id="sector-filter",
                        options=[{"label": "All Sectors", "value": ""}],
                        value="",
                        clearable=False,
                        style={
                            "background": CARD,
                            "border": f"1px solid {BORDER}",
                            "borderRadius": "10px",
                            "color": TEXT,
                            "width": "200px"
                        }
                    ),
                ]),
            ]),
            html.Div(id="screener-progress", className="mb-2xl"),
            dcc.Loading(
                id="screener-loading",
                type="default",
                color=BLUE,
                children=[
                    html.Div(id="screener-table-container", className="screener-table-wrap", children=[
                        html.Div("Loading screener data...", className="text-center p-4xl text-muted")
                    ])
                ]
            ),
        ]),
        # ── Tab: Analyze ─────────────────────────────────────────────────────────
        html.Div(id="tab-analyze", className="main-content", children=[
            html.Div(className="search-section", children=[
                html.Div(className="search-container", children=[
                    html.Div(className="search-input-wrapper", children=[
                        dcc.Input(
                            id="ticker-input",
                            type="text",
                            placeholder="Enter stock ticker (e.g. KO, JNJ, XOM)",
                            debounce=False,
                            className="ticker-input",
                            disabled=False
                        ),
                        html.Button("Analyze", id="analyze-btn", className="analyze-btn", disabled=False)
                    ]),
                    html.Div(id="status-msg", className="status-msg"),
                ]),
            ]),
            html.Div(id="history-section", className="history-section"),
        
            dcc.Loading(
                id="analysis-loading",
                type="default",
                color=BLUE,
                children=[
                    html.Div(id="analysis-content", children=[])
                ]
            ),
            # ── Add to Portfolio panel (shown after analysis completes) ──────────
            html.Div(id="add-to-portfolio-panel",children=[
                html.Div(className="portfolio-add-panel", children=[
                    html.Div(className="portfolio-add-header", children=[
                        html.Span("💼", className="text-2xl"),
                        html.Span("Add to Portfolio", className="font-semibold text-lg"),
                    ]),
                    html.Div(className="portfolio-add-controls", children=[
                        dcc.Dropdown(
                            id="portfolio-select-dropdown",
                            placeholder="Select or create portfolio…",
                            clearable=True,
                            className="min-w-220",
                        ),
                        dcc.Input(
                            id="portfolio-new-name",
                            type="text",
                            placeholder="Or type new portfolio name…",
                            className="max-w-220 ticker-input"
                        ),
                        dcc.Input(
                            id="portfolio-shares-input",
                            type="number",
                            placeholder="Shares (min 5)",
                            min=5,
                            step=1,
                            className="ticker-input max-w-130"
                        ),
                        html.Button("Add", id="portfolio-add-btn", className="analyze-btn", n_clicks=0),
                    ]),
                    html.Div(id="portfolio-add-msg", style={"fontSize": "13px", "marginTop": "6px"}),
                ])
            ]),
        ]),
        # ── Tab: Portfolios ──────────────────────────────────────────────────────
        html.Div(id="tab-portfolio", className="main-content", children=[
            # Top toolbar: portfolio switcher + create + compare
            html.Div(className="screener-toolbar", children=[
                html.Div(className="screener-controls", children=[
                    dcc.Dropdown(
                        id="portfolio-active-dropdown",
                        placeholder="Select a portfolio…",
                        clearable=False,
                        className="min-w-240",
                    ),
                    html.Button("＋ New Portfolio", id="portfolio-new-btn",
                                className="load-btn", n_clicks=0),
                    html.Button("🗑 Delete", id="portfolio-delete-btn",
                                className="load-btn",
                                style={"background": "#2a1a1a", "borderColor": "#ff1744"},
                                n_clicks=0),
                ]),
                html.Div(className="screener-controls", children=[
                    html.Label("Compare:", style={"fontSize": "13px", "color": "#9e9e9e"}),
                    dcc.Dropdown(
                        id="portfolio-compare-dropdown",
                        placeholder="Add portfolio to compare…",
                        clearable=True,
                        className="min-w-200",
                    ),
                ]),
            ]),
            # New portfolio name modal (inline, hidden by default)
            html.Div(id="portfolio-create-panel", className="hidden", children=[
                html.Div(className="portfolio-add-panel", children=[
                    html.Span("Name your portfolio:", className="text-primary"),
                    dcc.Input(id="portfolio-create-name", type="text",
                              placeholder="e.g. Value Picks Q1",
                              className="ticker-input max-w-240"),
                    html.Button("Create", id="portfolio-create-confirm-btn",
                                className="analyze-btn", n_clicks=0),
                    html.Button("Cancel", id="portfolio-create-cancel-btn",
                                className="load-btn", n_clicks=0),
                    html.Div(id="portfolio-create-msg",
                             style={"fontSize": "13px", "color": "#ff1744"}),
                ])
            ]),
            html.Div(id="portfolio-msg", style={"fontSize": "13px", "padding": "4px 0 8px"}),
            # Main portfolio content (holdings + run sim button)
            dcc.Loading(type="default", color="#448aff", children=[
                html.Div(id="portfolio-content", children=[
                    html.Div("Select or create a portfolio to get started.",
                             style={"textAlign": "center", "padding": "60px", "color": "#9e9e9e"})
                ])
            ]),
            # Simulation results (charts)
            html.Div(id="portfolio-sim-results", children=[]),
        ]),
        # ── Tab: Factor Lab ─────────────────────────────────────────────────────
        html.Div(id="tab-factorlab", className="main-content", style={"display": "none"}, children=[
            html.Div(className="app-header", style={"marginBottom": "24px"}, children=[
                html.Div("🧪", className="app-header-icon"),
                html.Div(className="app-header-content", children=[
                    html.H1("Factor Weight Lab"),
                    html.P(
                        "Adjust factor weights and backtest your custom scoring model "
                        "against your analysed stocks. Compares custom weights vs default "
                        "ENHANCED_WEIGHTS vs SPY buy-and-hold."
                    ),
                ])
            ]),

            html.Div(className="screener-toolbar", children=[
                html.Div(className="screener-controls", style={"flexWrap": "wrap", "gap": "20px"}, children=[
                    html.Div([
                        html.Label("Top N stocks", style={"fontSize": "12px", "color": "#9e9e9e"}),
                        dcc.Slider(id="fb-top-n", min=3, max=20, step=1, value=10,
                                   marks={3: "3", 5: "5", 10: "10", 15: "15", 20: "20"},
                                   tooltip={"placement": "bottom", "always_visible": False}),
                    ], style={"width": "200px"}),
                    html.Div([
                        html.Label("Backtest years", style={"fontSize": "12px", "color": "#9e9e9e"}),
                        dcc.Slider(id="fb-years", min=1, max=10, step=1, value=5,
                                   marks={1: "1", 3: "3", 5: "5", 7: "7", 10: "10"},
                                   tooltip={"placement": "bottom", "always_visible": False}),
                    ], style={"width": "200px"}),
                    html.Button("▶ Run Backtest", id="fb-run-btn", className="analyze-btn",
                                n_clicks=0, style={"alignSelf": "flex-end"}),
                    html.Div(id="fb-status", style={"alignSelf": "flex-end", "fontSize": "13px",
                                                     "color": "#9e9e9e"}),
                ]),
            ]),

            html.Div(className="scorecard", style={"marginTop": "16px"}, children=[
                html.Div("Factor Weights — drag sliders to reshape the model", className="scorecard-header"),
                html.Div(style={"display": "grid",
                                "gridTemplateColumns": "repeat(auto-fill, minmax(280px, 1fr))",
                                "gap": "20px", "padding": "16px 18px"}, children=[
                    *[
                        html.Div([
                            html.Div(style={"display": "flex", "justifyContent": "space-between",
                                            "marginBottom": "4px"}, children=[
                                html.Label(lbl, style={"fontSize": "13px", "fontWeight": "600"}),
                            ]),
                            dcc.Slider(
                                id=f"fb-w-{key}",
                                min=0, max=40, step=1,
                                value=round(scorer.ENHANCED_WEIGHTS.get(key, 0) * 100),
                                marks={0: "0", 10: "10", 20: "20", 30: "30", 40: "40"},
                                tooltip={"placement": "bottom", "always_visible": True},
                            ),
                        ])
                        for key, lbl in [
                            ("graham",            "Graham / Value"),
                            ("quality",           "Quality"),
                            ("momentum",          "Momentum"),
                            ("profitability",     "Profitability"),
                            ("fcf_quality",       "FCF Quality"),
                            ("earnings_revision", "Earnings Revision"),
                            ("capital_allocation","Capital Allocation"),
                            ("growth_quality",    "Growth Quality"),
                            ("risk",              "Risk"),
                            ("altman",            "Altman Safety"),
                        ]
                    ],
                ]),
                html.Div(id="fb-weight-sum-display",
                         style={"padding": "8px 18px 14px", "fontSize": "12px",
                                "color": "#9e9e9e", "fontStyle": "italic"},
                         children="Weight sum: 100% ✓"),
            ]),

            dcc.Loading(type="default", color="#448aff", children=[
                html.Div(id="fb-results", children=[])
            ]),
        ]),

        # Legal footer (ISSUE_013) — routes are placeholders until ToS/Privacy pages exist.
        html.Div(className="app-footer", style={
            "textAlign": "center", "padding": "16px", "fontSize": "11px", "color": "#9e9e9e"
        }, children=[
            html.Span("© Factor Research · "),
            html.A("Terms of Service", href="/terms", style={"color": "#9e9e9e"}),
            html.Span(" · "),
            html.A("Privacy Policy", href="/privacy", style={"color": "#9e9e9e"}),
            html.Span(" · Not financial advice."),
        ]),

        # Stores
        dcc.Store(id="screener-cache"),
        dcc.Store(id="analysis-store"),
        dcc.Store(id="screener-sort-store", data={"col": "composite_score", "asc": False}),
        dcc.Store(id="screener-page-store", data=1, storage_type="session"),  # current page in screener table
        dcc.Store(id="search-history-store"),
        dcc.Store(id="screener-click-ticker"),   # symbol clicked in screener table
        dcc.Store(id="portfolio-refresh-store", data=0),  # increment to trigger refresh
        dcc.Store(id="active-analysis-symbol"),           # symbol currently analyzed
        dcc.Store(id="screener-ready-store",  data=0),    # bumped once when loading completes
        dcc.Store(id="screener-viewed-store", data=[]),   # symbols the user has analyzed
        dcc.Store(id="screener-scroll-pos", data=0, storage_type="session"),  # remembered scroll position for screener tab
        # interval disabled=True once loading finishes to stop constant re-renders
        dcc.Interval(id="screener-progress-interval", interval=2000, disabled=True),
        # fires once 600ms after page load to render already-cached screener data
        # and re-enable the progress interval so a post-refresh render always works
        dcc.Interval(id="page-load-interval", interval=600, max_intervals=1, disabled=False),
        # polls the screener tab's scroll position so it can be restored on tab switch
        dcc.Interval(id="screener-scroll-poll-interval", interval=1000, disabled=False),
        dcc.Loading(id="loading", type="circle", color=BLUE, children=html.Div(id="loading-trigger"))
    ])
