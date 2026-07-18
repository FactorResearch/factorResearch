from __future__ import annotations

from http import HTTPStatus

import flask
from werkzeug.exceptions import HTTPException

from codes.core.errors import classify_exception
from codes.services.audit_journal import audit_journal

ERROR_PAGE_COPY = {
    400: {
        "eyebrow": "Bad request",
        "title": "That request is malformed.",
        "message": "The page understood the destination, but the request data was not valid.",
        "action": "Return home",
    },
    401: {
        "eyebrow": "Authentication required",
        "title": "Sign in to continue.",
        "message": "This research area is private and needs an authenticated session.",
        "action": "Go to sign in",
    },
    403: {
        "eyebrow": "Access restricted",
        "title": "This area is not available on your current access level.",
        "message": "Your session is valid, but this resource requires different permissions.",
        "action": "Review plans",
    },
    404: {
        "eyebrow": "Not found",
        "title": "This research page does not exist.",
        "message": "The ticker, snapshot, or route could not be found in Cenvarn.",
        "action": "Open screener",
    },
    500: {
        "eyebrow": "Server error",
        "title": "The research engine hit an unexpected error.",
        "message": "No private details were exposed. Try again, or return to the screener.",
        "action": "Return home",
    },
}


def register_error_pages(server: flask.Flask) -> None:
    for status_code in ERROR_PAGE_COPY:
        server.register_error_handler(status_code, _render_error)

    server.register_error_handler(Exception, _render_unhandled_error)


def _render_unhandled_error(error: Exception):
    if isinstance(error, HTTPException):
        return _render_error(error)
    current_app = flask.current_app
    structured = classify_exception(error)
    current_app.logger.exception("Unhandled server error", extra={"error_code": structured.code})
    audit_journal.record(
        "error_classified",
        action="unhandled_request",
        severity=structured.definition.severity.value.upper(),
        outcome="failure",
        details={"error_code": structured.code, "category": structured.definition.category.value},
    )
    return render_error_page(500, error), 500


def _render_error(error: Exception):
    status_code = getattr(error, "code", 500)
    if status_code not in ERROR_PAGE_COPY:
        try:
            reason = HTTPStatus(status_code).phrase
        except ValueError:
            reason = "Request failed"
        return flask.Response(f"{status_code} {reason}\n", status=status_code, mimetype="text/plain")
    return render_error_page(status_code, error), status_code


def render_error_page(status_code: int, error: Exception | None = None) -> str:
    copy = ERROR_PAGE_COPY.get(status_code, ERROR_PAGE_COPY[500])
    reason = HTTPStatus(status_code).phrase
    template_name = f"errors/{status_code}.html"
    return flask.render_template(
        template_name,
        status_code=status_code,
        reason=reason,
        request_path=flask.request.path,
        error_description=_safe_description(error),
        **copy,
    )


def _safe_description(error: Exception | None) -> str:
    if not isinstance(error, HTTPException):
        return ""
    return str(error.description or "")
