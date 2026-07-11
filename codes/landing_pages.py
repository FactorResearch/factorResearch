"""Trackable pre- and post-launch marketing landing pages."""

from __future__ import annotations

import random

import flask

from codes.services import product_analytics


VARIANTS = {
    "pre-a": {"phase": "pre", "style": "pre-a"},
    "pre-b": {"phase": "pre", "style": "pre-b"},
    "post-a": {"phase": "post", "style": "post-a"},
    "post-b": {"phase": "post", "style": "post-b"},
}


def register_landing_pages(server: flask.Flask) -> None:
    @server.route("/landing")
    def landing_ab():
        phase = flask.request.args.get("phase", "post").lower()
        phase = phase if phase in {"pre", "post"} else "post"
        key = f"landing_variant_{phase}"
        variant = flask.session.get(key)
        if variant not in VARIANTS or VARIANTS[variant]["phase"] != phase:
            variant = random.choice([f"{phase}-a", f"{phase}-b"])
            flask.session[key] = variant
        return flask.redirect(flask.url_for("landing_variant", variant=variant))

    @server.route("/landing/<variant>")
    def landing_variant(variant: str):
        config = VARIANTS.get(variant)
        if not config:
            flask.abort(404)
        product_analytics.track_event("", "landing_viewed", {"variant": variant, "phase": config["phase"]})
        return flask.render_template("landing.html", variant=variant, **config)
