"""Trackable pre- and post-launch marketing landing pages."""

from __future__ import annotations

import flask

from codes.services import product_analytics
from codes.services import waitlist


VARIANTS = {
    "pre-b": {"phase": "pre", "style": "pre-b"},
    "post-a": {"phase": "post", "style": "post-a"},
    "post-b": {"phase": "post", "style": "post-b"},
}


def register_landing_pages(server: flask.Flask) -> None:
    @server.route("/landing/waitlist", methods=["POST"])
    def landing_waitlist():
        variant = flask.request.form.get("variant", "pre-b")
        if variant != "pre-b":
            flask.abort(400)
        try:
            result = waitlist.subscribe(flask.request.form.get("email", ""), variant)
        except waitlist.WaitlistEmailError:
            result = "email_unavailable"
        except Exception as exc:
            flask.current_app.logger.warning("Waitlist signup failed: %s: %s", type(exc).__name__, exc)
            result = "email_unavailable"
        product_analytics.track_event("", "waitlist_submission", {"variant": variant, "result": result})
        return flask.redirect(flask.url_for("landing_variant", variant=variant, waitlist=result))

    @server.route("/landing")
    def landing_entry():
        phase = flask.request.args.get("phase", "pre").lower()
        variant = "post-b" if phase == "post" else "pre-b"
        return flask.redirect(flask.url_for("landing_variant", variant=variant))

    @server.route("/landing/<variant>")
    def landing_variant(variant: str):
        config = VARIANTS.get(variant)
        if not config:
            flask.abort(404)
        product_analytics.track_event("", "landing_viewed", {"variant": variant, "phase": config["phase"]})
        return flask.render_template("landing.html", variant=variant, **config)
