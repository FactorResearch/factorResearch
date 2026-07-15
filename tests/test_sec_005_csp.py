import base64
import hashlib
import re

from codes.app import server


def test_csp_hashes_every_inline_script_without_unsafe_script_execution():
    response = server.test_client().get("/")
    policy = response.headers["Content-Security-Policy"]
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", response.get_data(as_text=True), re.I | re.S)

    assert "script-src 'self'" in policy
    assert "script-src 'self' 'unsafe-inline'" not in policy
    assert "style-src-attr 'unsafe-inline'" in policy
    for script in scripts:
        if script.strip():
            digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in policy
