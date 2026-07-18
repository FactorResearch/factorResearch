"""Acceptance tests for ISSUE_058 authorization and safe action boundaries."""

import pytest

from codes.services import operations_console, provider_gateway


def test_actions_require_exact_confirmation_and_strict_boolean(monkeypatch):
    with pytest.raises(ValueError, match="confirmation"):
        operations_console.execute("cache.clear_local", actor="admin", confirmation="yes")
    with pytest.raises(ValueError, match="boolean"):
        operations_console.execute(
            "feature.kill_switch",
            actor="admin",
            confirmation="confirm:feature.kill_switch",
            parameters={"feature": "analysis", "enabled": "true"},
        )


def test_provider_reset_is_allowlisted_and_audited(monkeypatch):
    monkeypatch.setattr(provider_gateway, "_states", {"sec": {"failures": 4, "opened_at": 12.0}})
    result = operations_console.execute(
        "provider.reset_circuit",
        actor="admin",
        confirmation="confirm:provider.reset_circuit",
        parameters={"provider": "sec"},
    )
    assert result == {"provider": "sec", "reset": True}
    assert provider_gateway.health()["sec"] == {"failures": 0, "opened_at": 0.0}


def test_unknown_or_destructive_actions_are_rejected():
    with pytest.raises(ValueError, match="allowlisted"):
        operations_console.execute("database.drop", actor="admin", confirmation="confirm:database.drop")


def test_admin_endpoint_fails_closed(monkeypatch):
    from codes.app import server

    monkeypatch.delenv("OPERATIONS_ADMIN_USER_IDS", raising=False)
    response = server.test_client().get("/_internal/admin")
    assert response.status_code == 404
