"""Public Company Data research pages backed by Track E evidence."""

from __future__ import annotations

import html
import re

import flask

from codes.data import db, temporal
from codes.routes import standalone_shell


company_data_pages = flask.Blueprint("company_data_pages", __name__)
_SYMBOL = re.compile(r"^[A-Z0-9.-]{1,24}$")


def _value(value) -> str:
    return html.escape(str(value)) if value not in (None, "") else "Not available"


@company_data_pages.get("/data/<symbol>")
def company_data(symbol: str):
    ticker = symbol.strip().upper()
    if not _SYMBOL.fullmatch(ticker):
        flask.abort(404)
    identity = temporal.resolve_security("TICKER", ticker, market_code="CA" if ticker.endswith(".TO") else "US")
    if not identity:
        cached = db.get_analysis(ticker) or {}
        identity = {"security_id": None, "legal_name": cached.get("name") or ticker, "market_code": cached.get("market_code") or ("CA" if ticker.endswith(".TO") else "US"), "status": "coverage pending"}
    security_id = identity["security_id"]
    actions = temporal.list_corporate_actions(security_id) if security_id else []
    restatements = temporal.list_restatements(security_id) if security_id else []
    history = temporal.company_data_history(security_id) if security_id else {"identifiers": [], "filings": [], "universes": []}
    identifiers = "".join(
        f"<li><strong>{_value(row.get('namespace'))}</strong> {_value(row.get('identifier'))} <small>{_value(row.get('source'))}</small></li>"
        for row in history["identifiers"]
    ) or "<li>No additional identifiers are stored.</li>"
    filings = "".join(
        f"<tr><td>{_value(row.get('filed_at'))}</td><td>{_value(row.get('form_type'))}</td><td>{_value(row.get('period_end'))}</td><td>{_value(row.get('source'))}</td></tr>"
        for row in history["filings"]
    ) or '<tr><td colspan="4">No sourced filings are stored yet.</td></tr>'
    universes = "".join(
        f"<tr><td>{_value(row.get('name'))}</td><td>{_value(row.get('valid_from'))}</td><td>{_value(row.get('valid_to') or 'Current')}</td><td>{_value(row.get('source'))}</td></tr>"
        for row in history["universes"]
    ) or '<tr><td colspan="4">No sourced index memberships are stored.</td></tr>'
    action_rows = "".join(
        f"<tr><td>{_value(row.get('effective_date'))}</td><td>{_value(row.get('action_type'))}</td>"
        f"<td>{_value(row.get('ratio') or row.get('amount'))}</td><td>{_value(row.get('source'))}</td></tr>"
        for row in actions
    ) or '<tr><td colspan="4">No sourced corporate actions are stored yet.</td></tr>'
    restatement_rows = "".join(
        f"<tr><td>{_value(row.get('period_end'))}</td><td>{_value(row.get('fact_name'))}</td>"
        f"<td>{_value(row.get('original_value'))}</td><td>{_value(row.get('latest_value'))}</td></tr>"
        for row in restatements
    ) or '<tr><td colspan="4">No sourced restatements are stored.</td></tr>'
    title = f"{identity['legal_name']} Data History | FactorResearch"
    body = f"""<!doctype html><html lang="en">{standalone_shell.head(title)}<body class="app-container company-data-page">
{standalone_shell.header("analyze")}<main class="company-data-main"><nav class="company-data-breadcrumbs" aria-label="Breadcrumb"><a href="/">FactorResearch</a> / <a href="/?tab=analyze">Analyze</a> / Data History</nav>
<header class="company-data-hero"><p class="company-data-kicker">Company Data</p><h1>{_value(identity['legal_name'])} <span>{_value(ticker)}</span></h1>
<p>Source-backed identity, filing, restatement and corporate-action history. Missing data is never inferred.</p></header>
<div class="company-data-grid"><section class="company-data-section" aria-labelledby="identity"><h2 id="identity">Security identity</h2><div class="company-data-metrics">
<span>Market · {_value(identity.get('market_code'))}</span><span>Exchange · {_value(identity.get('exchange_code'))}</span>
<span>Currency · {_value(identity.get('currency'))}</span><span>Status · {_value(identity.get('status'))}</span></div></section>
<section class="company-data-section" aria-labelledby="identifiers"><h2 id="identifiers">Identifiers</h2><ul>{identifiers}</ul></section>
<section class="company-data-section company-data-section--wide" aria-labelledby="filings"><h2 id="filings">Filing history</h2><div class="company-data-table-wrap"><table><thead><tr><th>Filed</th><th>Form</th><th>Period</th><th>Source</th></tr></thead><tbody>{filings}</tbody></table></div></section>
<section class="company-data-section" aria-labelledby="actions"><h2 id="actions">Corporate actions</h2><div class="company-data-table-wrap"><table><thead><tr><th>Date</th><th>Type</th><th>Ratio / amount</th><th>Source</th></tr></thead><tbody>{action_rows}</tbody></table></div></section>
<section class="company-data-section" aria-labelledby="restatements"><h2 id="restatements">Financial restatements</h2><div class="company-data-table-wrap"><table><thead><tr><th>Period</th><th>Fact</th><th>Original</th><th>Latest</th></tr></thead><tbody>{restatement_rows}</tbody></table></div></section>
<section class="company-data-section company-data-section--wide" aria-labelledby="universes"><h2 id="universes">Index membership</h2><div class="company-data-table-wrap"><table><thead><tr><th>Universe</th><th>From</th><th>To</th><th>Source</th></tr></thead><tbody>{universes}</tbody></table></div></section></div>
</main>{standalone_shell.footer()}</body></html>"""
    return flask.Response(body, mimetype="text/html")
