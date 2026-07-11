"""
Graham Score App — Full Quant Version
Pure Python / Dash with SEC EDGAR + Alpha Vantage
Enhanced score uses the orthogonal factor weights defined in codes.engine.scorer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Allow both `python app.py` (direct) and `python -m codes.app` (module) execution.
# Inserts the project root so that `codes.*` package imports resolve in both cases.

import dash
import functools
import flask
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:
    Limiter = None
    get_remote_address = None
from codes import auth
from codes import billing
from codes import security
from flask import render_template
from codes.data import sec_data
from codes.engine import screener, universe
from codes.routes.analyze import analyze_pages
from codes.landing_pages import register_landing_pages
from codes.services.analysis_snapshot_service import ensure_schema_if_configured
from codes.services.analytics_bootstrap import build_head_snippets
from codes.services import product_analytics
from codes.sitemap_generator import generate_analysis_sitemap

import codes.portfolio as portfolio_engine
from codes.app_modules.analysis import is_production
from codes.app_modules.layout import build_layout
from codes.app_modules.rate_limit import clear_rate_limits_for_user
from codes.app_modules.session import get_user_id, invalidate_portfolio_cache
# ── App Init ──────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="FactorResearch",
    suppress_callback_exceptions=True,
    assets_folder='../assets',
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}]
)
server = app.server
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key and os.environ.get("FLASK_ENV", "").lower() == "production":
    raise RuntimeError("FLASK_SECRET_KEY must be set in production to protect session cookies.")
server.secret_key = secret_key or os.urandom(24)
server.register_blueprint(analyze_pages)
try:
    ensure_schema_if_configured()
except Exception as e:
    print(f"Analysis snapshot schema init failed: {type(e).__name__}: {e}")


auth.init_auth(server)
billing.init_billing(server)
register_landing_pages(server)
@server.route("/account/delete", methods=["POST"])
def delete_account():
    user_id = get_user_id()

    summary = portfolio_engine.delete_all_user_data(user_id)
    security.audit_log_access("DELETE_ACCOUNT", "user_data", user_id)

    # Purge in-memory/session-scoped state tied to this user
    invalidate_portfolio_cache()
    clear_rate_limits_for_user(user_id)

    auth.clear_authenticated_user()
    flask.session.clear()

    security.SECURITY_LOGGER.info(f"Right-to-erasure completed for user {user_id}")
    return flask.jsonify(summary)

_LEGAL_PLACEHOLDER_NOTICE = (
    "<p style='color:#b00;font-weight:700;'>⚠️ PLACEHOLDER TEXT — NOT REVIEWED BY LEGAL COUNSEL. "
    "Do not rely on this page for compliance. Replace before public launch.</p>"
)

@server.route("/terms")
def terms_page():
    return render_template(
        "terms.html",
        legal_notice=_LEGAL_PLACEHOLDER_NOTICE
    )

@server.route("/privacy")
def privacy_page():
    return render_template(
        "privacy.html",
        legal_notice=_LEGAL_PLACEHOLDER_NOTICE,
        analytics_opt_out=product_analytics.is_tracking_opted_out(),
    )


@server.route("/privacy/analytics", methods=["GET", "POST"])
def update_analytics_preference():
    if flask.request.method == "POST":
        payload = flask.request.get_json(silent=True) or flask.request.form or {}
        raw_value = payload.get("opt_out")
        opt_out = str(raw_value).lower() in {"1", "true", "yes", "on"}
        product_analytics.set_tracking_opt_out(opt_out)
    return flask.jsonify(product_analytics.get_tracking_context())

@server.route("/sitemap-analysis.xml")
def analysis_sitemap():
    base_url = flask.request.url_root.rstrip("/")
    return flask.Response(generate_analysis_sitemap(base_url), mimetype="application/xml")

@server.route("/robots.txt")
def robots_txt():
    base_url = flask.request.url_root.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /analyze/\n"
        f"Sitemap: {base_url}/sitemap-analysis.xml\n"
    )
    return flask.Response(body, mimetype="text/plain")

# ── Initialize Comprehensive Security ──────────────────────────────────────────
security.init_security(server)

# Initialize Flask-Limiter if available (best-effort; dev may omit package)
if Limiter is not None:
    limiter = Limiter(app=server, key_func=get_remote_address, default_limits=[])
else:
    limiter = None

@server.after_request
def _log_errors(response):
    # Security headers are now handled by security.init_security()
    # This function is kept for backward compatibility and additional logging
    return response

# Patch Dash's internal callback handler to log exceptions minimally (no stack traces)
_orig_dispatch = app.server.dispatch_request if hasattr(app.server, 'dispatch_request') else None
_orig_cb = dash.Dash.callback
def _logging_callback(self, *args, **kwargs):
    decorator = _orig_cb(self, *args, **kwargs)
    def wrap(func):
        @functools.wraps(func)
        def inner(*a, **kw):
            try:
                return func(*a, **kw)
            except Exception as e:
                # Log only exception type and short message to avoid leaking secrets
                print(f"[CALLBACK ERROR] in {func.__name__}: {type(e).__name__}: {str(e)}", flush=True)
                # Raise a generic error to avoid exposing internal details to UI
                raise Exception("Internal server error")
        return decorator(inner)
    return wrap
dash.Dash.callback = _logging_callback

# Importing tab modules registers their Dash callbacks.
from codes.app_modules.tabs import analyze, factor_lab, navigation, portfolio, pricing, screener as screener_tab  # noqa: F401

# ── Mobile touch fix: eliminate 300ms tap delay on all buttons ───────────────
app.index_string = app.index_string.replace(
    '</head>',
    '<style>'
    'button,a,[role="button"]{'
    'touch-action:manipulation;'
    '-webkit-tap-highlight-color:rgba(0,0,0,0.08);'
    'cursor:pointer;'
    '}'
    '</style></head>'
)
app.index_string = app.index_string.replace(
    '</head>',
    '<script>'
    '(function(){'
    '  let savedScroll = 0;'
    '  window.addEventListener("orientationchange", function(){'
    '    savedScroll = window.scrollY;'
    '  });'
    '  window.addEventListener("resize", function(){'
    '    if (savedScroll > 0) {'
    '      requestAnimationFrame(function(){'
    '        window.scrollTo(0, savedScroll);'
    '      });'
    '    }'
    '  });'
    '})();'
    '</script></head>'
)
app.index_string = app.index_string.replace(
    '</head>',
    build_head_snippets() + '</head>'
)

app.index_string = app.index_string.replace(
    '</head>',
    '<script>'
    'const APP_VERSION = "v3.4";'  # bump this on each deploy
    'if (localStorage.getItem("app_version") !== APP_VERSION) {'
    '    localStorage.setItem("app_version", APP_VERSION);'
    '    location.reload(true);'
    '}'
    '</script></head>'
)

app.layout = build_layout()
screener_tab.register_clientside_callbacks(app)

# ── Startup ───────────────────────────────────────────────────────────────────
def startup():
    print("\n🚀 Graham Score — Quant Edition")
    from codes.data import db
    db.init_db()
    sec_data.get_ticker_map()
    universe.get_universe()
    results = screener.load_cached_only()
    print(f"✅ {len(results)} cached stocks ready\n")

startup()

if __name__ == "__main__":
   
    
    app.run(
        host="0.0.0.0" if is_production() else "127.0.0.1",
        debug=not is_production(),
        port=int(os.environ.get("PORT", 8050)),
    )
