"""Flask adapter for the framework-neutral product analytics context port."""

from __future__ import annotations

import os

import flask

_SESSION_OPT_OUT_KEY = "analytics_opt_out"


class FlaskAnalyticsContext:
    """Expose only analytics-relevant request/session state."""

    def anonymous_id(self) -> str | None:
        if not flask.has_request_context():
            return None
        value = flask.session.get("_uid") or flask.session.get("_authenticated_user_id")
        return value if isinstance(value, str) else None

    def authenticated_user_id(self) -> str | None:
        if not flask.has_request_context():
            return None
        value = flask.session.get("_authenticated_user_id")
        return value if isinstance(value, str) else None

    def page_path(self) -> str | None:
        if not flask.has_request_context():
            return None
        try:
            return str(flask.request.path)
        except Exception:
            return None

    def is_opted_out(self) -> bool:
        if os.environ.get("ANALYTICS_OPT_OUT", "").lower() in {"1", "true", "yes"}:
            return True
        return bool(flask.has_request_context() and flask.session.get(_SESSION_OPT_OUT_KEY))

    def set_opt_out(self, opt_out: bool) -> None:
        if flask.has_request_context():
            flask.session[_SESSION_OPT_OUT_KEY] = bool(opt_out)
