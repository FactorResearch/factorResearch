from codes.app import server


def test_trusted_hosts_reject_unknown_host_before_route_processing():
    previous = server.config.get("TRUSTED_HOSTS")
    server.config["TRUSTED_HOSTS"] = ["localhost", "127.0.0.1"]
    try:
        response = server.test_client().get("/", base_url="http://attacker.invalid")
    finally:
        server.config["TRUSTED_HOSTS"] = previous

    assert response.status_code == 400
    assert "intrinsic_iq_session" not in response.headers.get("Set-Cookie", "")


def test_trusted_hosts_allow_configured_host_with_port():
    previous = server.config.get("TRUSTED_HOSTS")
    server.config["TRUSTED_HOSTS"] = ["localhost", "127.0.0.1"]
    try:
        response = server.test_client().get("/robots.txt", base_url="http://127.0.0.1:8050")
    finally:
        server.config["TRUSTED_HOSTS"] = previous

    assert response.status_code == 200
