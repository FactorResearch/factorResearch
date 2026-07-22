from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from codes.app_modules import layout
from codes.app_modules.tabs import navigation, profile
from codes.data import db
from codes.services import user_settings


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row=None):
        self.row_factory = None
        self.calls = []
        self._row = row

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _FakeResult(self._row)


@contextmanager
def _ctx(conn):
    yield conn


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_by_id(child, target_id)
        if found is not None:
            return found
    return None


def test_topbar_exposes_personalized_profile_button():
    topbar = layout._topbar()
    profile_btn = _find_by_id(topbar, "profile-menu-btn")
    profile_link = _find_by_id(topbar, "profile-nav-link")

    assert profile_btn is not None
    assert _find_by_id(topbar, "profile-menu-label").children == "Hi there"
    assert profile_link.children == "More settings"


def test_profile_path_shows_profile_page_and_sets_active_state():
    with patch.object(navigation.dash, "ctx", SimpleNamespace(triggered_id="url")):
        result = navigation.switch_tabs(0, 0, 0, 0, 0, None, None, "/profile")

    assert result[:6] == (
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "block"},
    )
    assert result[6:] == (
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn",
        "topbar-nav-btn tab-btn active",
    )


def test_render_profile_menu_label_uses_display_name(monkeypatch):
    monkeypatch.setattr(profile, "get_user_id", lambda: "amin_user")
    monkeypatch.setattr(profile.account_service, "display_name", lambda _user_id: "Amin User")

    assert profile.render_profile_menu_label("/") == "Hi Amin User"


def test_user_settings_use_users_connection(monkeypatch):
    users_conn = _FakeConn(row={"settings_json": {"appearance": {"theme": "dark"}}})
    monkeypatch.setattr(db, "_users_initialized", True)
    monkeypatch.setattr(db, "_users_conn", lambda *_args, **_kwargs: _ctx(users_conn))

    result = db.get_user_settings("u1")

    assert result == {"appearance": {"theme": "dark"}}
    assert len(users_conn.calls) == 1


def test_user_settings_normalization_fills_profile_defaults():
    settings = user_settings.normalize_user_settings({"appearance": {"theme": "dark"}})

    assert settings["appearance"]["theme"] == "dark"
    assert settings["notifications"]["product_updates"] is True
    assert settings["saved_screeners"] == []


def test_save_current_screener_persists_market_and_filters(monkeypatch):
    monkeypatch.setattr(profile, "get_user_id", lambda: "user-1")
    monkeypatch.setattr(
        profile.account_service,
        "add_saved_screener",
        lambda user_id, **kwargs: {"saved_screeners": [{"id": "value", **kwargs}]},
    )

    result = profile.save_current_screener(
        1,
        "Value",
        {"market": "CA", "sector": "Technology", "indexes": ["sp500"]},
    )

    assert result[0]["saved_screeners"][0]["market"] == "CA"
    assert result[0]["saved_screeners"][0]["sector"] == "Technology"
    assert result[1] == "Current screener saved."
