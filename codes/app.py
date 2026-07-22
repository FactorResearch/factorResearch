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
import hmac
import re
from markupsafe import escape
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:
    Limiter = None
    get_remote_address = None
from codes import auth
from codes import billing
from codes import security
from codes.api import api_v1
from codes.composition import compose_runtime
from codes.core.config import is_production
from codes.core.request_context import RequestContext, bind_context, reset_context
from flask import render_template
from codes.data import sec_data
from codes.engine import universe
from codes.routes.analyze import analyze_pages
from codes.routes.charts import chart_pages
from codes.error_pages import register_error_pages
from codes.landing_pages import register_landing_pages
from codes.services.analytics_bootstrap import build_head_snippets
from codes.services import product_analytics
from codes.services import performance_metrics, provider_gateway
from codes.services.operations_dashboard import snapshot as operations_snapshot
from codes.services.analysis_snapshot_service import ensure_schema_if_configured
from codes.services import operations_console
from codes.services import account_service, analysis_jobs, component_cache, screener_service
from codes.services.operational_controller import classify_runtime_health, controller
from codes.services.company_logo_cache import get_or_fetch_logo
from codes.sitemap_generator import generate_analysis_sitemap

from codes.app_modules.composition import compose_dash_ui
from codes.app_modules.rate_limit import clear_rate_limits_for_user
from codes.app_modules.session import get_user_id, invalidate_portfolio_cache
# ── App Init ──────────────────────────────────────────────────────────────────
runtime = compose_runtime()
app = dash.Dash(
    __name__,
    title="Cenvarn",
    suppress_callback_exceptions=True,
    assets_folder='../assets',
    # Source SCSS and standalone-route styles stay directly addressable, but
    # must not be injected into the interactive Dash shell.
    assets_ignore=(
        r".*\.scss$|"
        r"^(company_analysis|error_pages|landing|landing_pre|legal_pages|waitlist)\.css$"
    ),
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1, viewport-fit=cover"},
        {"name": "theme-color", "content": "#0f1b2d"},
        {"name": "mobile-web-app-capable", "content": "yes"},
        {"name": "apple-mobile-web-app-capable", "content": "yes"},
        {"name": "apple-mobile-web-app-status-bar-style", "content": "black-translucent"},
    ]
)
server = app.server
server.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_REQUEST_BYTES", str(2 * 1024 * 1024)))
trusted_hosts = [host.strip() for host in os.environ.get("TRUSTED_HOSTS", "").split(",") if host.strip()]
if trusted_hosts:
    server.config["TRUSTED_HOSTS"] = trusted_hosts
secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key and is_production():
    raise RuntimeError("FLASK_SECRET_KEY must be set in production to protect session cookies.")
server.secret_key = secret_key or os.urandom(24)


@server.before_request
def reject_untrusted_host():
    # Accessing request.host invokes Flask/Werkzeug's TRUSTED_HOSTS validation.
    flask.request.host


server.register_blueprint(analyze_pages)
server.register_blueprint(chart_pages)
server.register_blueprint(api_v1)


auth.init_auth(server)
billing.init_billing(server)
register_landing_pages(server)
register_error_pages(server)


@server.route("/manifest.webmanifest")
def web_manifest():
    return flask.jsonify({
        "name": "Cenvarn",
        "short_name": "Cenvarn",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f1b2d",
        "theme_color": "#0f1b2d",
        "description": "Fast, model-driven company research.",
    }), 200, {"Content-Type": "application/manifest+json", "Cache-Control": "public, max-age=86400"}


@server.route("/service-worker.js")
def service_worker():
    script = """
const CACHE = 'factorresearch-shell-v2';
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE)));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== location.origin || !url.pathname.startsWith('/assets/')) return;
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(event.request);
    if (cached) return cached;
    const response = await fetch(event.request);
    if (response.ok) cache.put(event.request, response.clone());
    return response;
  }));
});
"""
    return flask.Response(script, mimetype="application/javascript", headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@server.route("/_internal/performance")
def internal_performance():
    expected = os.environ.get("INTERNAL_METRICS_TOKEN")
    supplied = flask.request.headers.get("X-Internal-Metrics-Token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        flask.abort(404)
    from codes.data import analytics_db, db
    from codes.services import analysis_snapshot_service
    controller.register_probe(
        "providers",
        lambda: classify_runtime_health("providers", provider_gateway.health()),
    )
    controller.register_probe(
        "analysis-queue",
        lambda: classify_runtime_health("analysis-queue", analysis_jobs.health()),
    )
    return flask.jsonify({
        "performance": performance_metrics.snapshot(),
        "providers": provider_gateway.health(),
        "component_cache": component_cache.stats(),
        "jobs": analysis_jobs.health(),
        "operational": controller.summary(),
        "database_pools": {
            "application": db.pool_health(),
            "analytics": analytics_db.pool_health(),
            "snapshots": analysis_snapshot_service.pool_health(),
        },
    })


@server.route("/_internal/operations")
def internal_operations():
    """Serve the read-only operations view to explicitly allowlisted admins."""
    if not auth.is_operations_admin():
        flask.abort(404)
    try:
        limit = int(flask.request.args.get("limit", "50"))
    except ValueError:
        return flask.jsonify({"error": "limit must be an integer"}), 400
    if limit < 1 or limit > 100:
        return flask.jsonify({"error": "limit must be between 1 and 100"}), 400
    return flask.jsonify(
        operations_snapshot(
            search=flask.request.args.get("search", ""),
            limit=limit,
        )
    )


@server.route("/_internal/admin", methods=["GET"])
def internal_admin():
    """Return the authorized console catalogue and current operational state."""
    actor = auth.get_authenticated_user_id()
    if not auth.is_operations_admin(actor):
        flask.abort(404)
    return flask.jsonify({"console": operations_console.describe(), "operations": operations_snapshot()})


@server.route("/_internal/admin/actions", methods=["POST"])
def internal_admin_action():
    """Execute one confirmed, authorized, reversible console action."""
    actor = auth.get_authenticated_user_id()
    if not auth.is_operations_admin(actor):
        flask.abort(404)
    payload = flask.request.get_json(silent=True)
    if not isinstance(payload, dict):
        return flask.jsonify({"error": "JSON object is required"}), 400
    try:
        result = operations_console.execute(
            payload.get("action", ""),
            actor=actor or "",
            confirmation=payload.get("confirmation", ""),
            parameters=payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {},
        )
    except ValueError as exc:
        return flask.jsonify({"error": str(exc)}), 400
    except Exception:
        return flask.jsonify({"error": "administrative action unavailable"}), 503
    return flask.jsonify({"ok": True, "result": result})


_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


@server.before_request
def start_request_metrics():
    supplied = flask.request.headers.get("X-Request-ID", "")
    request_id = supplied if _REQUEST_ID.fullmatch(supplied) else runtime.ids.new_id()
    supplied_correlation = flask.request.headers.get("X-Correlation-ID", "")
    correlation_id = (
        supplied_correlation if _REQUEST_ID.fullmatch(supplied_correlation) else request_id
    )
    context = RequestContext.create(request_id=request_id, correlation_id=correlation_id)
    flask.g.request_context_token = bind_context(context)
    flask.g.request_id = context.request_id
    flask.g.correlation_id = context.correlation_id
    flask.g.operation_id = context.operation_id
    flask.g.request_started = runtime.clock.monotonic()


@server.after_request
def finish_request_metrics(response):
    started = getattr(flask.g, "request_started", runtime.clock.monotonic())
    route = flask.request.url_rule.rule if flask.request.url_rule else "unmatched"
    performance_metrics.record_request(
        route,
        flask.request.method,
        response.status_code,
        (runtime.clock.monotonic() - started) * 1000,
    )
    response.headers["X-Request-ID"] = getattr(
        flask.g, "request_id", runtime.ids.new_id()
    )
    response.headers["X-Correlation-ID"] = getattr(flask.g, "correlation_id", "")
    response.headers["X-Operation-ID"] = getattr(flask.g, "operation_id", "")
    return response


@server.teardown_request
def clear_request_context(_error):
    """Restore the caller context after every request, including failures."""
    token = getattr(flask.g, "request_context_token", None)
    if token is not None:
        reset_context(token)


@server.route("/company-logo")
def cached_company_logo():
    symbol = flask.request.args.get("symbol", "?").strip().upper()[:24]
    company_name = flask.request.args.get("name", symbol).strip()[:160] or symbol
    logo = get_or_fetch_logo(symbol, company_name)
    if logo:
        response = flask.Response(bytes(logo["image_bytes"]), mimetype=logo["mime_type"])
        response.set_etag(logo["content_hash"])
        response.cache_control.public = True
        response.cache_control.max_age = 86400
        return response.make_conditional(flask.request)

    initials = escape(symbol[:2] or "?")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">'
        '<rect width="96" height="96" fill="#16243a"/>'
        f'<text x="48" y="56" text-anchor="middle" fill="#9cafc7" '
        f'font-family="sans-serif" font-size="28" font-weight="700">{initials}</text></svg>'
    )
    response = flask.Response(svg, mimetype="image/svg+xml")
    response.cache_control.public = True
    response.cache_control.max_age = 300
    return response


@server.route("/account/delete", methods=["POST"])
@auth.require_auth
def delete_account():
    user_id = get_user_id()

    summary = account_service.delete_account_data(user_id)
    security.audit_log_access("DELETE_ACCOUNT", "user_data", user_id)

    # Purge in-memory/session-scoped state tied to this user
    invalidate_portfolio_cache()
    clear_rate_limits_for_user(user_id)

    auth.clear_authenticated_user()
    flask.session.clear()

    security.SECURITY_LOGGER.info(f"Right-to-erasure completed for user {user_id}")
    return flask.jsonify(summary)

@server.route("/terms")
def terms_page():
    return render_template("terms.html")

@server.route("/methodology")
def methodology_page():
    return render_template("methodology.html")

@server.route("/privacy")
def privacy_page():
    return render_template(
        "privacy.html",
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


@server.route("/analytics/vitals", methods=["POST"])
def collect_web_vitals():
    if product_analytics.is_tracking_opted_out():
        return ("", 204)
    payload = flask.request.get_json(silent=True) or {}
    if not security.validate_json_payload(payload, max_size=4096):
        return flask.jsonify({"error": "invalid telemetry payload"}), 400
    route = product_analytics.normalize_page_path(payload.get("route")) or "/unknown"
    accepted = performance_metrics.record_web_vital(
        payload.get("name", ""),
        payload.get("value"),
        route=route,
        device=str(payload.get("device") or "unknown"),
        navigation_type=str(payload.get("navigation_type") or "navigate"),
    )
    return ("", 204) if accepted else (flask.jsonify({"error": "unsupported metric"}), 400)


@server.route("/analytics/ux-events", methods=["POST"])
def collect_ux_event():
    if product_analytics.is_tracking_opted_out():
        return ("", 204)
    payload = flask.request.get_json(silent=True) or {}
    if not security.validate_json_payload(payload, max_size=2048):
        return flask.jsonify({"error": "invalid telemetry payload"}), 400
    allowed = {
        "model_detail_expanded",
        "methodology_opened",
        "weak_link_inspected",
        "form_validation_failure",
        "recovery_retry_started",
    }
    event_name = str(payload.get("event") or "")
    if event_name not in allowed:
        return flask.jsonify({"error": "unsupported event"}), 400
    product_analytics.track_event(
        get_user_id(), event_name, product_analytics.sanitize_metadata(payload.get("metadata") or {})
    )
    return ("", 204)

@server.route("/sitemap-analysis.xml")
def analysis_sitemap():
    base_url = (os.environ.get("PUBLIC_BASE_URL") or flask.request.url_root).rstrip("/")
    return flask.Response(generate_analysis_sitemap(base_url), mimetype="application/xml")

@server.route("/robots.txt")
def robots_txt():
    base_url = (os.environ.get("PUBLIC_BASE_URL") or flask.request.url_root).rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /analyze/\n"
        f"Sitemap: {base_url}/sitemap-analysis.xml\n"
    )
    return flask.Response(body, mimetype="text/plain")

# ── Initialize Comprehensive Security ──────────────────────────────────────────
security.init_security(server)


@server.errorhandler(413)
def request_too_large(_error):
    return flask.jsonify({"error": "request too large"}), 413


@server.errorhandler(429)
def request_rate_limited(_error):
    return flask.jsonify({"error": "rate limit exceeded"}), 429


@server.before_request
def apply_endpoint_body_limit():
    if flask.request.path == "/billing/webhook":
        flask.request.max_content_length = int(os.environ.get("STRIPE_WEBHOOK_MAX_BYTES", str(256 * 1024)))

# Initialize Flask-Limiter if available (best-effort; dev may omit package)
if Limiter is not None:
    rate_limit_storage = os.environ.get("RATELIMIT_STORAGE_URI") or os.environ.get("REDIS_URL")
    if is_production() and not rate_limit_storage:
        raise RuntimeError("RATELIMIT_STORAGE_URI or REDIS_URL is required in production.")
    limiter = Limiter(
        app=server,
        key_func=get_remote_address,
        default_limits=[os.environ.get("DEFAULT_RATE_LIMIT", "600 per minute")],
        storage_uri=rate_limit_storage or "memory://",
    )
    for endpoint, limit in {
        "/_dash-update-component": "240 per minute",
        "_stripe_webhook": "120 per minute",
        "landing_waitlist": "5 per minute",
        "cached_company_logo": "60 per minute",
        "_checkout": "20 per minute",
        "_portal": "20 per minute",
        "dev_impersonate": "20 per minute",
    }.items():
        if endpoint in server.view_functions:
            server.view_functions[endpoint] = limiter.limit(limit)(server.view_functions[endpoint])
else:
    limiter = None

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
                performance_metrics.record_failure(f"callback:{func.__name__}", e)
                # Log only exception type and short message to avoid leaking secrets
                print(f"[CALLBACK ERROR] in {func.__name__}: {type(e).__name__}: {str(e)}", flush=True)
                # Raise a generic error to avoid exposing internal details to UI
                raise Exception("Internal server error")
        return decorator(inner)
    return wrap
dash.Dash.callback = _logging_callback

compose_dash_ui(app, head_snippets=build_head_snippets())

# ── Startup ───────────────────────────────────────────────────────────────────
def startup():
    print("\n🚀 Graham Score — Quant Edition")
    from codes.data import db
    # ISSUE_126: normal web processes verify release state and never mutate
    # schema. The dedicated release phase must finish before traffic starts.
    db.verify_runtime_databases()
    ensure_schema_if_configured()
    sec_data.get_ticker_map()
    universe.get_universe()
    results = screener_service.load_cached_only()
    from codes.services.analysis_scheduler import start_background_maintenance
    start_background_maintenance()
    print(f"✅ {len(results)} cached stocks ready\n")

if os.environ.get("APP_SKIP_STARTUP") != "1":
    startup()

if __name__ == "__main__":
   
    
    # Production ingress must reach the process; the edge controls public exposure.
    app.run(
        host="0.0.0.0" if is_production() else "127.0.0.1",  # nosec B104
        debug=not is_production(),
        port=int(os.environ.get("PORT", 8050)),
    )
