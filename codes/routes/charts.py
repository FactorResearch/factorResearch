from __future__ import annotations

import flask

from codes.services import chart_service, stock_analysis

chart_pages = flask.Blueprint("chart_pages", __name__)
_PUBLIC_ANALYSIS_CHARTS = {"eps_history", "price_history", "dividend_history"}


@chart_pages.get("/charts/<ticker>/<chart_type>")
def analysis_chart_dataset(ticker: str, chart_type: str):
    if chart_type not in _PUBLIC_ANALYSIS_CHARTS:
        flask.abort(404)
    data = stock_analysis.get_cached_analysis(ticker.upper())
    if not data:
        flask.abort(404)
    dataset = chart_service.get_analysis_chart_dataset(
        data,
        chart_type,
        period=flask.request.args.get("period", chart_service.DEFAULT_PERIOD),
    )
    status = 503 if dataset.get("error") else 200
    return flask.jsonify(dataset), status
