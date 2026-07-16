"""Dash layout composition."""

from dash import dcc, html

from codes.app_modules.company_identity import logo_attribution
from codes.app_modules.design_system.primitives import (
    button,
    checkbox_group,
    input_control,
    link,
    loading_container,
    radio_group,
    select_control,
    slider,
)
from codes.data.us_indices import US_INDEX_DEFINITIONS
from codes.engine import scorer

from .config import BLUE
from .screener_markets import (
    DEFAULT_SCREENER_MARKET,
    available_screener_markets,
    get_screener_market,
)


def _screener_market_links(active_market=DEFAULT_SCREENER_MARKET):
    active_code = get_screener_market(active_market).code
    return html.Nav(
        id="screener-market-nav",
        className="screener-country-tabs",
        **{"aria-label": "Screener market"},
        children=[
            link(
                [
                    html.Img(src=market.flag_src, alt="", className="screener-country-flag"),
                    html.Span(market.short_label, className="screener-country-label"),
                ],
                id={"type": "screener-market-link", "index": market.code},
                href=market.path,
                refresh=False,
                title=market.label,
                className="screener-country-tab" + (" active" if market.code == active_code else ""),
            )
            for market in available_screener_markets()
        ],
    )


def _screener_index_pills(selected=None):
    selected = set(selected or [])
    return [
            button(
                index["label"],
                id={"type": "index-filter-pill", "index": index["value"]},
                variant="ghost",
            className="screener-index-pill" + (" active" if index["value"] in selected else ""),
            n_clicks=0,
            type="button",
        )
        for index in US_INDEX_DEFINITIONS
    ]


def _topbar():
    return html.Header(id="topbar", className="topbar", children=[
        html.Div(className="topbar-brand", children=[
            html.Img(src="/assets/logo.svg", alt="Research Factor", className="topbar-logo"),
            html.Span("FactorResearch", className="topbar-title"),
        ]),
        html.Nav(className="topbar-nav", role="tablist", **{"aria-label": "Primary navigation"}, children=[
            button("Screener", id="tab-screener-btn", className="topbar-nav-btn tab-btn active", role="tab", **{"data-tab": "screener", "aria-controls": "tab-screener", "aria-selected": "true"}),
            button("Analyze",  id="tab-analyze-btn",  className="topbar-nav-btn tab-btn", role="tab", **{"data-tab": "analyze", "aria-controls": "tab-analyze", "aria-selected": "false"}),
            button("Portfolio", id="tab-portfolio-btn", className="topbar-nav-btn tab-btn", role="tab", **{"data-tab": "portfolio", "aria-controls": "tab-portfolio", "aria-selected": "false"}),
            button("Factor Lab", id="tab-factorlab-btn", className="topbar-nav-btn tab-btn", role="tab", **{"data-tab": "factorlab", "aria-controls": "tab-factorlab", "aria-selected": "false"}),
            button("Pricing", id="tab-pricing-btn", className="topbar-nav-btn tab-btn", role="tab", **{"data-tab": "pricing", "aria-controls": "tab-pricing", "aria-selected": "false"}),
        ]),
        html.Div(className="topbar-actions", children=[
            html.Div(className="profile-menu-shell", children=[
                button(
                    id="profile-menu-btn",
                    className="topbar-nav-btn tab-btn",
                    n_clicks=0,
                    type="button",
                    **{"aria-expanded": "false", "aria-controls": "profile-quick-panel"},
                    children=[
                        html.Span("👤", className="mr-6"),
                        html.Span("Hi there", id="profile-menu-label"),
                        html.Span("▾", id="profile-menu-chevron", className="profile-menu-chevron ml-6"),
                    ],
                ),
                html.Div(id="profile-quick-panel", className="scorecard is-hidden", **{"data-ds-overlay": "popup", "data-ds-close-controller": "profile-menu-btn"}, children=[
                    html.Div("Quick settings", className="scorecard-header"),
                    html.Div(className="p-16", children=[
                        html.Label("Setting", htmlFor="profile-quick-section-dropdown", className="fs-13 clr-muted"),
                        select_control(
                            id="profile-quick-section-dropdown",
                            options=[
                                {"label": "Account", "value": "account"},
                                {"label": "Subscription", "value": "subscription"},
                                {"label": "Appearance", "value": "appearance"},
                                {"label": "Notifications", "value": "notifications"},
                                {"label": "Saved portfolios", "value": "portfolios"},
                                {"label": "Saved screeners", "value": "screeners"},
                                {"label": "Security", "value": "security"},
                            ],
                            value="appearance",
                            clearable=False,
                            className="mb-16 min-w-240",
                        ),
                        html.Label("Theme", htmlFor="profile-quick-theme-dropdown", className="fs-13 clr-muted"),
                        select_control(
                            id="profile-quick-theme-dropdown",
                            options=[
                                {"label": "System", "value": "system"},
                                {"label": "Light", "value": "light"},
                                {"label": "Dark", "value": "dark"},
                            ],
                            clearable=False,
                            className="mb-16 min-w-220",
                        ),
                        html.Div(id="profile-quick-summary", className="mb-12 text-muted"),
                        html.Div(id="profile-quick-detail", className="mb-16"),
                        html.Div(className="d-flex gap-12 flex-wrap", children=[
                            button("Save", id="profile-quick-save-btn", className="analyze-btn", n_clicks=0),
                            link("More settings", id="profile-nav-link", href="/profile", className="load-btn"),
                        ]),
                        html.Div(id="profile-quick-msg", className="fs-13 mt-6", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                    ]),
                ]),
            ]),
            html.Div(id="theme-dummy", className="d-none"),
        ]),
    ])


def _legal_terms_content():
    return [
        html.P("FactorResearch provides research tools, scoring models, screeners, portfolio analytics, and educational content for self-directed investors.", className="legal-modal-lead"),
        html.H3("No Investment Advice"),
        html.P("The Service is not a registered investment adviser, broker-dealer, tax adviser, or legal adviser. Scores, rankings, forecasts, alerts, and model outputs are informational only and are not personalized recommendations."),
        html.H3("Market Data and Model Risk"),
        html.P("Financial data may come from public filings, third-party providers, cached calculations, and derived models. Data can be delayed, incomplete, inaccurate, or unavailable. Past performance and backtests do not guarantee future results."),
        html.H3("Accounts, Payments, and Access"),
        html.P("You are responsible for account security and lawful use. Paid features depend on billing status and product access rules. Plan access may change if billing, abuse prevention, or product requirements change."),
        html.H3("Limitation of Liability"),
        html.P("FactorResearch is provided as is without warranties. We are not liable for investment losses, missed opportunities, data outages, provider errors, or indirect damages arising from use of the Service."),
    ]


def _legal_privacy_content():
    return [
        html.P("We collect account identifiers, authentication session data, portfolio names and holdings, feature usage, billing status, waitlist submissions, and product analytics events.", className="legal-modal-lead"),
        html.H3("How Information Is Used"),
        html.P("Information is used to operate the app, save portfolios, enforce feature limits, process billing status, prevent abuse, improve product flows, and troubleshoot reliability issues."),
        html.H3("Analytics and Providers"),
        html.P("Product analytics can be disabled from the full Privacy Policy page. We may use infrastructure, authentication, analytics, email, market-data, and payment providers to operate the Service. We do not sell personal information."),
        html.H3("Retention and Deletion"),
        html.P("We keep data while needed to provide the Service, satisfy billing or security requirements, and maintain product records. Account deletion removes portfolios and session-linked user data through the account deletion flow."),
        html.H3("Security"),
        html.P("We use reasonable technical controls, but no internet service can be guaranteed secure. Do not submit private brokerage passwords or sensitive financial account credentials."),
    ]


def _legal_modal(modal_id, title, full_page_href, children):
    return html.Section(id=modal_id, className="legal-modal-overlay", **{"data-ds-overlay": "modal"}, children=[
        html.A(className="legal-modal-backdrop", href="#", tabIndex=-1, **{"aria-label": "Close legal dialog", "data-ds-close": "true"}),
        html.Div(className="legal-modal-card", role="dialog", **{"aria-modal": "true", "aria-labelledby": f"{modal_id}-title"}, children=[
            html.Div(className="legal-modal-header", children=[
                html.Div([
                    html.P("FactorResearch legal", className="legal-modal-kicker"),
                    html.H2(title, id=f"{modal_id}-title"),
                ]),
                html.A("Close", href="#", className="legal-modal-close", **{"data-ds-close": "true"}),
            ]),
            html.Div(className="legal-modal-body", children=children),
            html.Div(className="legal-modal-actions", children=[
                html.A("Open full page", href=full_page_href, className="legal-modal-primary"),
                html.A("Close", href="#", className="legal-modal-secondary", **{"data-ds-close": "true"}),
            ]),
        ]),
    ])


def build_layout():
    return html.Div(className="app-container", children=[
        dcc.Location(id="url", refresh=False),
        html.A("Skip to main content", href="#tab-screener", className="skip-link", id="skip-to-content"),
        _topbar(),
        # ── Tab: Screener ────────────────────────────────────────────────────────
        html.Div(id="tab-screener", className="screener-content block", role="tabpanel", tabIndex=-1, **{"aria-labelledby": "tab-screener-btn"}, children=[
            html.Div(className="screener-toolbar", children=[
                html.Details(className="screener-filter-drawer", children=[
                    html.Summary(
                        html.Span("Filters (0 active)", id="screener-filter-summary"),
                        className="screener-filter-summary",
                    ),
                    html.Div(className="screener-controls flex gap-lg align-items-center", children=[
                    html.Div(className="screener-index-filter", children=[
                        html.Label("Filter by index:", className="text-sm text-muted"),
                        html.Div(
                            id="index-filter-pill-container",
                            className="screener-index-pills",
                            children=_screener_index_pills(),
                        ),
                        dcc.Store(id="index-filter", data=[]),
                    ]),
                    html.Div(className="filters",children=[
                    html.Label("Filter by sector:", htmlFor="sector-filter", className="text-sm text-muted"),
                    select_control(
                        id="sector-filter",
                        options=[{"label": "All Sectors", "value": ""}],
                        value="",
                        clearable=False,
                        className="bg-card br-10 clr-text",
                    ),
                    ]),
                    button("Clear all", id="screener-clear-all-btn", variant="secondary", className="screener-clear-all", n_clicks=0),
                    ]),
                ]),
                html.Details(className="screener-view-controls", children=[
                    html.Summary("Table view", className="screener-view-summary"),
                    html.Div(className="screener-view-panel", children=[
                        html.Fieldset(className="screener-column-chooser", children=[
                            html.Legend("Visible columns"),
                            checkbox_group(
                                id="screener-visible-columns",
                                options=[
                                    {"label": "Ticker", "value": "ticker", "disabled": True},
                                    {"label": "Company", "value": "company"},
                                    {"label": "Sector", "value": "sector"},
                                    {"label": "Market cap", "value": "market_cap"},
                                    {"label": "Composite", "value": "composite_score"},
                                    {"label": "Fair value", "value": "graham_number"},
                                    {"label": "Economic moat", "value": "buffett_iv"},
                                    {"label": "Updated", "value": "updated_at"},
                                    {"label": "Verdict", "value": "verdict"},
                                ],
                                value=["ticker", "company", "sector", "market_cap", "composite_score", "graham_number", "buffett_iv", "updated_at", "verdict"],
                                persistence=True,
                                persistence_type="local",
                            ),
                        ]),
                        html.Fieldset(className="screener-density-control", children=[
                            html.Legend("Row density"),
                            radio_group(
                                id="screener-table-density",
                                options=[
                                    {"label": "Comfortable", "value": "comfortable"},
                                    {"label": "Compact", "value": "compact"},
                                ],
                                value="comfortable",
                                persistence=True,
                                persistence_type="local",
                                inline=True,
                            ),
                        ]),
                    ]),
                ]),
            ]),
            html.Div(id="screener-progress", className="mb-2xl"),
            html.Div(className="screener-market-shell", children=[
                _screener_market_links(),
                loading_container(
                    id="screener-loading",
                    type="default",
                    color=BLUE,
                    delay_show=250,
                    delay_hide=200,
                    show_initially=False,
                    children=[
                        html.Div(id="screener-table-container", className="screener-table-wrap", **{"aria-busy": "false", "data-adaptive-loading": "true"}, children=[
                            html.Div("Loading screener data...", className="text-center p-4xl text-muted")
                        ])
                    ]
                ),
                html.Div(className="sr-only", role="status", **{"aria-live": "polite", "data-loading-for": "screener-table-container", "data-loading-label": "Updating screener rows"}),
                html.Div(
                    id="screener-quick-peek-shell",
                    className="quick-peek-shell",
                    children=[
                        button(
                            id="quick-peek-backdrop",
                            className="quick-peek-backdrop",
                            n_clicks=0,
                            type="button",
                            **{"aria-label": "Close quick peek"},
                        ),
                        html.Aside(
                            id="screener-quick-peek-panel",
                            className="quick-peek-panel",
                            role="dialog",
                            **{"aria-modal": "false", "aria-labelledby": "quick-peek-title"},
                            children=[
                                html.Div(
                                    className="quick-peek-panel-inner",
                                    children=[
                                        html.Div(
                                            className="quick-peek-panel-top",
                                            children=[
                                                html.Div(
                                                    className="quick-peek-panel-copy",
                                                    children=[
                                                        html.Div("Quick Peek", className="quick-peek-kicker"),
                                                        html.H3("Stock snapshot", id="quick-peek-title", className="quick-peek-title"),
                                                    ],
                                                ),
                                                button(
                                                    "Close",
                                                    id="quick-peek-close-btn",
                                                    className="quick-peek-close-btn",
                                                    n_clicks=0,
                                                    type="button",
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            id="screener-quick-peek-content",
                                            className="quick-peek-content",
                                        ),
                                    ],
                                )
                            ],
                        ),
                    ],
                ),
            ]),
        ]),
        # ── Tab: Analyze ─────────────────────────────────────────────────────────
        html.Div(id="tab-analyze", className="main-content", role="tabpanel", tabIndex=-1, **{"aria-labelledby": "tab-analyze-btn"}, children=[
            html.Div(className="analyze-header", children=[
                html.Div(className="analyze-ticker-input", children=[
                    html.Label("Stock ticker", htmlFor="ticker-input", className="sr-only"),
                    input_control(
                        id="ticker-input",
                        type="text",
                        placeholder="Enter stock ticker (e.g. KO, JNJ, XOM)",
                        debounce=False,
                        className="ticker-input",
                        disabled=False
                    ),
                    button("Analyze", id="analyze-btn", className="analyze-btn", disabled=False)
                ]),
                html.Span(id="analyze-current", className="analyze-current"),
                html.Div(id="status-msg", className="status-msg w-full", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
            ]),
            html.Div(id="history-section", className="history-section"),

            loading_container(
                id="analysis-loading",
                type="default",
                color=BLUE,
                delay_show=250,
                delay_hide=200,
                show_initially=False,
                children=[
                    html.Div(id="analysis-content", **{"aria-busy": "false", "data-adaptive-loading": "true"}, children=[])
                ]
            ),
            html.Div(className="sr-only", role="status", **{"aria-live": "polite", "data-loading-for": "analysis-content", "data-loading-label": "Updating analysis sections"}),
            # ── Add to Portfolio panel (shown after analysis completes) ──────────
            html.Div(id="add-to-portfolio-panel", className="d-none", children=[
                html.Div(className="portfolio-add-panel", children=[
                    html.Div(className="portfolio-add-header", children=[
                        html.Span("💼", className="text-2xl"),
                        html.Span("Add to Portfolio", className="font-semibold text-lg"),
                    ]),
                    html.Div(className="portfolio-add-controls", children=[
                        html.Label("Portfolio", htmlFor="portfolio-select-dropdown", className="sr-only"),
                        select_control(
                            id="portfolio-select-dropdown",
                            placeholder="Select or create portfolio…",
                            clearable=True,
                            className="min-w-220",
                        ),
                        html.Label("New portfolio name", htmlFor="portfolio-new-name", className="sr-only"),
                        input_control(
                            id="portfolio-new-name",
                            type="text",
                            placeholder="Or type new portfolio name…",
                            className="max-w-220 ticker-input"
                        ),
                        html.Label("Number of shares", htmlFor="portfolio-shares-input", className="sr-only"),
                        input_control(
                            id="portfolio-shares-input",
                            type="number",
                            placeholder="Shares (min 5)",
                            min=5,
                            step=1,
                            className="ticker-input max-w-130"
                        ),
                        button("Add", id="portfolio-add-btn", className="analyze-btn", n_clicks=0),
                    ]),
                    html.Div(id="portfolio-add-msg", className="fs-13 mt-6", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                ])
            ]),
            html.Div(id="analysis-anchor-scroll-trigger", className="d-none"),
        ]),
        # ── Tab: Portfolios ──────────────────────────────────────────────────────
        html.Div(id="tab-portfolio", className="main-content", role="tabpanel", tabIndex=-1, **{"aria-labelledby": "tab-portfolio-btn"}, children=[
            # Top toolbar: portfolio switcher + create + compare
            html.Div(className="screener-toolbar", children=[
                html.Div(className="screener-controls", children=[
                    html.Label("Active portfolio", htmlFor="portfolio-active-dropdown", className="sr-only"),
                    select_control(
                        id="portfolio-active-dropdown",
                        placeholder="Select a portfolio…",
                        clearable=False,
                        persistence=True,
                        persistence_type="session",
                        className="min-w-240",
                    ),
                    button("＋ New Portfolio", id="portfolio-new-btn",
                                className="load-btn", n_clicks=0),
                    button("🗑 Delete", id="portfolio-delete-btn", variant="danger",
                                className="load-btn portfolio-delete-btn",
                                n_clicks=0),
                ]),
                html.Div(className="screener-controls", children=[
                    html.Label("Compare:", htmlFor="portfolio-compare-dropdown", className="fs-13 clr-muted"),
                    select_control(
                        id="portfolio-compare-dropdown",
                        placeholder="Add portfolio to compare…",
                        clearable=True,
                        persistence=True,
                        persistence_type="session",
                        className="min-w-200",
                    ),
                ]),
            ]),
            # New portfolio name modal (inline, hidden by default)
            html.Div(id="portfolio-create-panel", className="hidden", children=[
                html.Div(className="portfolio-add-panel", children=[
                    html.Label("Name your portfolio:", htmlFor="portfolio-create-name", className="text-primary"),
                    input_control(id="portfolio-create-name", type="text",
                              placeholder="e.g. Value Picks Q1",
                              className="ticker-input max-w-240"),
                    button("Create", id="portfolio-create-confirm-btn",
                                className="analyze-btn", n_clicks=0),
                    button("Cancel", id="portfolio-create-cancel-btn", variant="secondary",
                                className="load-btn", n_clicks=0),
                    html.Div(id="portfolio-create-msg",
                             className="fs-13 clr-red", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                ])
            ]),
            html.Div(id="portfolio-msg", className="portfolio-message fs-13", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
            # Main portfolio content (holdings + run sim button)
            loading_container(type="default", color=BLUE, delay_show=250, delay_hide=200, show_initially=False, children=[
                html.Div(id="portfolio-content", **{"aria-busy": "false", "data-adaptive-loading": "true"}, children=[
                    html.Div("Select or create a portfolio to get started.",
                             className="tac p-60 clr-muted")
                ])
            ]),
            html.Div(className="sr-only", role="status", **{"aria-live": "polite", "data-loading-for": "portfolio-content", "data-loading-label": "Updating portfolio holdings"}),
            # Simulation results (charts)
            html.Div(id="portfolio-sim-results", children=[]),
            dcc.Store(id="portfolio-job-store", storage_type="local"),
            dcc.Interval(id="portfolio-job-interval", interval=800, disabled=False),
        ]),
        # ── Tab: Factor Lab ─────────────────────────────────────────────────────
        html.Div(id="tab-factorlab", className="main-content is-hidden", role="tabpanel", tabIndex=-1, **{"aria-labelledby": "tab-factorlab-btn"}, children=[
            html.Div(className="app-header mb-24", children=[
                html.Div("🧪", className="app-header-icon", **{"aria-hidden": "true"}),
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
                html.Div(className="screener-controls flex-wrap gap-20", children=[
                    html.Div([
                        html.Label("Top N stocks", htmlFor="fb-top-n", className="fs-12 clr-muted"),
                        slider(id="fb-top-n", min=3, max=20, step=1, value=10,
                                   marks={3: "3", 5: "5", 10: "10", 15: "15", 20: "20"},
                                   tooltip={"placement": "bottom", "always_visible": False}),
                    ], className="control-width-200"),
                    html.Div([
                        html.Label("Backtest years", htmlFor="fb-years", className="fs-12 clr-muted"),
                        slider(id="fb-years", min=1, max=10, step=1, value=5,
                                   marks={1: "1", 3: "3", 5: "5", 7: "7", 10: "10"},
                                   tooltip={"placement": "bottom", "always_visible": False}),
                    ], className="control-width-200"),
                    button("▶ Run Backtest", id="fb-run-btn", className="analyze-btn as-end",
                                n_clicks=0),
                    html.Div(id="fb-status", className="as-end fs-13 clr-muted", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                ]),
            ]),

            html.Div(className="scorecard mt-16", children=[
                html.Div("Factor Weights — drag sliders to reshape the model", className="scorecard-header"),
                html.Div(className="factor-weight-grid d-grid gap-20", children=[
                    *[
                        html.Div([
                            html.Div(className="d-flex jc-between mb-4", children=[
                                html.Label(lbl, htmlFor=f"fb-w-{key}", className="fs-13 fw-600"),
                            ]),
                            slider(
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
                         className="factor-weight-summary fs-12 clr-muted fsi",
                         children="Weight sum: 100% ✓"),
                button("Reset default weights", id="fb-reset-weights-btn", variant="secondary", className="factor-reset-weights", n_clicks=0),
            ]),

            loading_container(type="default", color=BLUE, delay_show=250, delay_hide=200, show_initially=False, children=[
                html.Div(id="fb-results", **{"aria-busy": "false", "data-adaptive-loading": "true"}, children=[])
            ]),
            html.Div(className="sr-only", role="status", **{"aria-live": "polite", "data-loading-for": "fb-results", "data-loading-label": "Running factor backtest"}),
            dcc.Store(id="factor-job-store", storage_type="local"),
            dcc.Interval(id="factor-job-interval", interval=800, disabled=False),
        ]),
        html.Div(id="tab-pricing", className="main-content is-hidden", role="tabpanel", tabIndex=-1, **{"aria-labelledby": "tab-pricing-btn"}, children=[]),
        html.Div(id="profile-page", className="main-content is-hidden", role="main", tabIndex=-1, children=[
            html.Div(className="app-header mb-24", children=[
                html.Div("👤", className="app-header-icon", **{"aria-hidden": "true"}),
                html.Div(className="app-header-content", children=[
                    html.H1("Profile"),
                    html.P("Manage account details, subscription state, saved research settings, and reusable screener preferences."),
                ]),
            ]),
            html.Div(className="scorecard mb-16", children=[
                html.Div("Settings", className="scorecard-header"),
                html.Div(className="p-16", children=[
                    html.Label("Jump to setting", htmlFor="profile-section-dropdown", className="fs-13 clr-muted"),
                    select_control(
                        id="profile-section-dropdown",
                        options=[
                            {"label": "Account", "value": "account"},
                            {"label": "Subscription", "value": "subscription"},
                            {"label": "Appearance", "value": "appearance"},
                            {"label": "Notifications", "value": "notifications"},
                            {"label": "Saved portfolios", "value": "portfolios"},
                            {"label": "Saved screeners", "value": "screeners"},
                            {"label": "Security", "value": "security"},
                            {"label": "API keys", "value": "api_keys"},
                        ],
                        value="appearance",
                        clearable=False,
                        className="max-w-240 mb-16",
                    ),
                    html.Div(id="profile-section-summary", className="mb-12 text-muted"),
                    html.Label("Theme", htmlFor="profile-theme-dropdown", className="fs-13 clr-muted"),
                    select_control(
                        id="profile-theme-dropdown",
                        options=[
                            {"label": "System", "value": "system"},
                            {"label": "Light", "value": "light"},
                            {"label": "Dark", "value": "dark"},
                        ],
                        clearable=False,
                        className="max-w-220 mb-16",
                    ),
                    html.Label("Notifications", htmlFor="profile-notifications-checklist", className="fs-13 clr-muted"),
                    checkbox_group(
                        id="profile-notifications-checklist",
                        options=[
                            {"label": "Product updates", "value": "product_updates"},
                            {"label": "Research digest", "value": "research_digest"},
                            {"label": "Security alerts", "value": "security_alerts"},
                        ],
                        inline=False,
                        className="mb-16",
                    ),
                    button("Save settings", id="profile-save-settings-btn", className="analyze-btn", n_clicks=0),
                    html.Div(id="profile-settings-msg", className="fs-13 mt-6", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                ]),
            ]),
            html.Div(id="profile-screeners-panel", className="scorecard mb-16 is-hidden", children=[
                html.Div("Saved screeners", className="scorecard-header"),
                html.Div(className="p-16", children=[
                    html.Div(id="profile-saved-screeners-card", className="mb-16"),
                    input_control(
                        id="profile-save-screener-name",
                        type="text",
                        placeholder="Save current screener as…",
                        className="ticker-input max-w-240",
                    ),
                    html.Div(className="d-flex gap-12 flex-wrap mt-12", children=[
                        button("Save current screener", id="profile-save-screener-btn", className="analyze-btn", n_clicks=0),
                        select_control(
                            id="profile-saved-screener-select",
                            options=[],
                            placeholder="Select saved screener…",
                            clearable=True,
                            className="min-w-240",
                        ),
                        button("Delete saved screener", id="profile-delete-screener-btn", variant="danger", className="load-btn", n_clicks=0),
                    ]),
                    html.Div(id="profile-screener-msg", className="fs-13 mt-6", role="status", **{"aria-live": "polite", "aria-atomic": "true"}),
                ]),
            ]),
            html.Div(id="profile-detail-card", className="scorecard"),
        ]),

        _legal_modal("legal-terms", "Terms of Service", "/terms", _legal_terms_content()),
        _legal_modal("legal-privacy", "Privacy Policy", "/privacy", _legal_privacy_content()),

        # Legal footer
        html.Div(className="app-footer tac p-16 fs-11 clr-muted", children=[
            html.Span("© Factor Research · "),
            html.A("Terms of Service", href="#legal-terms", className="clr-muted"),
            html.Span(" · "),
            html.A("Privacy Policy", href="#legal-privacy", className="clr-muted"),
            html.Span(" · Not financial advice."),
            logo_attribution(),
        ]),

        # Stores
        dcc.Store(id="screener-cache"),
        dcc.Store(id="analysis-store"),
        dcc.Store(id="screener-sort-store", data={"col": "composite_score", "asc": False}),
        dcc.Store(id="screener-page-store", data=1, storage_type="session"),  # current page in screener table
        dcc.Store(id="search-history-store"),
        dcc.Store(id="screener-quick-peek-symbol"),
        dcc.Store(id="screener-open-analysis-symbol"),
        dcc.Store(id="portfolio-refresh-store", data=0),  # increment to trigger refresh
        dcc.Store(id="active-analysis-symbol"),           # symbol currently analyzed
        dcc.Store(id="upgrade-funnel-store", data=None),
        dcc.Store(id="user-settings-store", data=None),
        dcc.Store(
            id="screener-context-store",
            data={"market": DEFAULT_SCREENER_MARKET, "sector": "", "indexes": []},
        ),
        dcc.Store(id="screener-ready-store",  data=0),    # bumped once when loading completes
        dcc.Store(id="screener-viewed-store", data=[]),   # symbols the user has analyzed
        dcc.Store(id="screener-scroll-pos", data=0, storage_type="session"),  # remembered scroll position for screener tab
        html.Div(id="screener-scroll-restore-sink", className="is-hidden"),
        html.Div(id="screener-url-state-sink", className="is-hidden"),
        # interval disabled=True once loading finishes to stop constant re-renders
        dcc.Interval(id="screener-progress-interval", interval=2000, disabled=True),
        # fires once 600ms after page load to render already-cached screener data
        # and re-enable the progress interval so a post-refresh render always works
        dcc.Interval(id="page-load-interval", interval=600, max_intervals=1, disabled=False),
        # polls the screener tab's scroll position so it can be restored on tab switch
        dcc.Interval(id="screener-scroll-poll-interval", interval=1000, disabled=False),
        dcc.Interval(id="analysis-secondary-interval", interval=1200, disabled=False),
        loading_container(
            id="loading",
            type="circle",
            color=BLUE,
            delay_show=250,
            delay_hide=200,
            show_initially=False,
            children=html.Div(
                id="loading-trigger",
                **{"aria-busy": "false", "data-adaptive-loading": "true"},
            ),
        ),
        html.Div(
            className="sr-only",
            role="status",
            **{
                "aria-live": "polite",
                "data-loading-for": "loading-trigger",
                "data-loading-label": "Updating application state",
            },
        ),
    ])
