"""Flask adapter for the first public, versioned client contract."""

from __future__ import annotations

import re
from pathlib import Path

import flask

from codes import auth
from codes.api import contracts
from codes.core.errors import error_for_code
from codes.services import account_service, screener_service, stock_analysis

api_v1 = flask.Blueprint("api_v1", __name__, url_prefix="/api/v1")
_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,11}$")
_OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


def _request_id() -> str:
    return str(getattr(flask.g, "request_id", "unavailable"))


def _json(data: object, status: int = 200):
    return flask.jsonify(data), status


def _error(code: str, message: str, status: int):
    structured = error_for_code(code)
    return _json(
        contracts.error_response(structured.code, message, _request_id()),
        status,
    )


def _authenticated_user() -> str | None:
    return auth.get_authenticated_user_id()


def _page_parameters() -> tuple[int, int, int, bool] | None:
    try:
        page_size = int(flask.request.args.get("page_size", str(contracts.DEFAULT_PAGE_SIZE)))
    except ValueError:
        return None
    if page_size < 1 or page_size > contracts.MAX_PAGE_SIZE:
        return None
    cursor = flask.request.args.get("cursor", "")
    if cursor:
        try:
            offset = contracts.decode_cursor(cursor)
        except ValueError:
            return None
        return offset // page_size + 1, page_size, offset, True
    try:
        page = int(flask.request.args.get("page", "1"))
    except ValueError:
        return None
    if page < 1:
        return None
    return page, page_size, (page - 1) * page_size, False


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
    response = stock_analysis.get_cached_analysis_response(normalized)
    if response is None:
        return _error("not_found", "Analysis was not found.", 404)
    return _json(contracts.data_response(response.to_dict(), _request_id()))


@api_v1.get("/screener")
def screener():
    parameters = _page_parameters()
    if parameters is None:
        return _error(
            "invalid_pagination",
            f"page must be positive and page_size must be between 1 and {contracts.MAX_PAGE_SIZE}.",
            400,
        )
    page, page_size, start, cursor_mode = parameters
    rows = screener_service.get_results()
    items = [contracts.screener_resource(row) for row in rows[start : start + page_size]]
    end = start + len(items)
    return _json(
        contracts.collection_response(
            items,
            page,
            page_size,
            len(rows),
            _request_id(),
            next_cursor=contracts.encode_cursor(end) if cursor_mode and end < len(rows) else None,
            previous_cursor=contracts.encode_cursor(max(0, start - page_size))
            if cursor_mode and start > 0
            else None,
        )
    )


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
    page, page_size, start, cursor_mode = parameters
    include_deleted = flask.request.args.get("include_deleted", "false").lower() == "true"
    changed_since = flask.request.args.get("changed_since")
    if include_deleted or changed_since:
        rows = account_service.portfolio_summaries(
            user_id, include_deleted=include_deleted, changed_since=changed_since
        )
    else:
        rows = account_service.portfolio_summaries(user_id)
    items = [contracts.portfolio_summary(row) for row in rows[start : start + page_size]]
    end = start + len(items)
    return _json(
        contracts.collection_response(
            items,
            page,
            page_size,
            len(rows),
            _request_id(),
            next_cursor=contracts.encode_cursor(end) if cursor_mode and end < len(rows) else None,
            previous_cursor=contracts.encode_cursor(max(0, start - page_size))
            if cursor_mode and start > 0
            else None,
        )
    )


@api_v1.get("/billing")
def billing():
    user_id = _authenticated_user()
    if not user_id:
        return _error("unauthorized", "Authentication is required.", 401)
    resource = contracts.billing_resource(account_service.subscription_summary(user_id))
    return _json(contracts.data_response(resource, _request_id()))
