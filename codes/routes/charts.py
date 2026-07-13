from __future__ import annotations

import flask

from codes.data import db
from codes.services import chart_service

chart_pages = flask.Blueprint("chart_pages", __name__)
_PUBLIC_ANALYSIS_CHARTS = {"eps_history", "price_history", "dividend_history"}


@chart_pages.get("/charts/<ticker>/<chart_type>")
def analysis_chart_dataset(ticker: str, chart_type: str):
    if chart_type not in _PUBLIC_ANALYSIS_CHARTS:
        flask.abort(404)
    data = db.get_analysis(ticker.upper())
    if not data:
        flask.abort(404)
    dataset = chart_service.get_analysis_chart_dataset(
        data,
        chart_type,
        period=flask.request.args.get("period", chart_service.DEFAULT_PERIOD),
    )
    status = 503 if dataset.get("error") else 200
    return flask.jsonify(dataset), status
