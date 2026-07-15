from unittest.mock import patch

from codes.app import server


ORIGIN = {"Origin": "http://localhost"}


def test_global_body_limit_rejects_dash_payload_before_dispatch():
    response = server.test_client().post(
        "/_dash-update-component",
        data=b"x" * (2 * 1024 * 1024 + 1),
        content_type="application/json",
        headers=ORIGIN,
    )
    assert response.status_code == 413


def test_webhook_has_tighter_body_limit_before_signature_verification():
    with patch("codes.billing.stripe_client.construct_webhook_event") as construct:
        response = server.test_client().post(
            "/billing/webhook",
            data=b"x" * (256 * 1024 + 1),
            content_type="application/octet-stream",
        )
    assert response.status_code == 413
    construct.assert_not_called()


def test_waitlist_burst_is_rate_limited_before_more_writes():
    client = server.test_client()
    with patch("codes.landing_pages.waitlist.subscribe", return_value="confirmed") as subscribe:
        responses = [
            client.post(
                "/landing/waitlist",
                data={"variant": "pre-a", "email": f"user{index}@example.com"},
                headers={**ORIGIN, "X-Forwarded-For": "198.51.100.42"},
            )
            for index in range(6)
        ]
    assert [response.status_code for response in responses] == [302] * 5 + [429]
    assert subscribe.call_count == 5
