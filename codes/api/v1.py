"""Flask adapter for the first public, versioned client contract."""

from __future__ import annotations

import re
from pathlib import Path

import flask

from codes import auth
from codes.api import contracts
from codes.services import account_service, screener_service, stock_analysis

api_v1 = flask.Blueprint("api_v1", __name__, url_prefix="/api/v1")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")
_OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


def _request_id() -> str:
    return str(getattr(flask.g, "request_id", "unavailable"))


def _json(data: object, status: int = 200):
    return flask.jsonify(data), status


def _error(code: str, message: str, status: int):
    return _json(contracts.error_response(code, message, _request_id()), status)


def _authenticated_user() -> str | None:
    return auth.get_authenticated_user_id()


def _page_parameters() -> tuple[int, int] | None:
    try:
        page = int(flask.request.args.get("page", "1"))
        page_size = int(flask.request.args.get("page_size", str(contracts.DEFAULT_PAGE_SIZE)))
    except ValueError:
        return None
    if page < 1 or page_size < 1 or page_size > contracts.MAX_PAGE_SIZE:
        return None
    return page, page_size


@api_v1.get("/health")
def health():
    return _json(contracts.data_response({"status": "ok"}, _request_id()))


@api_v1.get("/openapi.yaml")
def openapi_document():
    return flask.send_file(_OPENAPI_PATH, mimetype="application/yaml", max_age=300)


@api_v1.get("/analysis/<symbol>")
def analysis(symbol: str):
    normalized = str(symbol or "").upper()
    if not _SYMBOL.fullmatch(normalized):
        return _error("invalid_request", "A valid market symbol is required.", 400)
    result = stock_analysis.get_cached_analysis(normalized)
    if not result or result.get("error"):
        return _error("not_found", "Analysis was not found.", 404)
    resource = contracts.analysis_resource(result, normalized)
    return _json(contracts.data_response(resource, _request_id()))


@api_v1.get("/screener")
def screener():
    parameters = _page_parameters()
    if parameters is None:
        return _error(
            "invalid_pagination",
            f"page must be positive and page_size must be between 1 and {contracts.MAX_PAGE_SIZE}.",
            400,
        )
    page, page_size = parameters
    rows = screener_service.get_results()
    start = (page - 1) * page_size
    items = [contracts.screener_resource(row) for row in rows[start : start + page_size]]
    return _json(contracts.collection_response(items, page, page_size, len(rows), _request_id()))


@api_v1.get("/account")
def account():
    user_id = _authenticated_user()
    if not user_id:
        return _error("unauthorized", "Authentication is required.", 401)
    resource = contracts.account_resource(
        {
            "display_name": account_service.display_name(user_id),
            "auth_provider": account_service.auth_provider(),
            "settings": account_service.get_settings(user_id),
        }
    )
    return _json(contracts.data_response(resource, _request_id()))


@api_v1.get("/portfolios")
def portfolios():
    user_id = _authenticated_user()
    if not user_id:
        return _error("unauthorized", "Authentication is required.", 401)
    parameters = _page_parameters()
    if parameters is None:
        return _error(
            "invalid_pagination",
            f"page must be positive and page_size must be between 1 and {contracts.MAX_PAGE_SIZE}.",
            400,
        )
    page, page_size = parameters
    rows = account_service.portfolio_summaries(user_id)
    start = (page - 1) * page_size
    items = [contracts.portfolio_summary(row) for row in rows[start : start + page_size]]
    return _json(contracts.collection_response(items, page, page_size, len(rows), _request_id()))


@api_v1.get("/billing")
def billing():
    user_id = _authenticated_user()
    if not user_id:
        return _error("unauthorized", "Authentication is required.", 401)
    resource = contracts.billing_resource(account_service.subscription_summary(user_id))
    return _json(contracts.data_response(resource, _request_id()))
