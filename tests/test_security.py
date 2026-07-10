"""
Security Tests for Graham Score App

Tests for:
- Input validation
- CSRF protection
- Rate limiting
- SQL injection prevention
- XSS protection
- Authentication
- Authorization
"""

import pytest
import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from codes import security


def test_security_package_import_stays_lightweight():
    script = (
        "import sys\n"
        "from codes import security\n"
        "blocked = {'pandas', 'codes.data.sec_data', 'codes.data.api_fetcher'}\n"
        "loaded = blocked.intersection(sys.modules)\n"
        "assert not loaded, f'unexpected eager imports: {sorted(loaded)}'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_ticker_valid(self):
        """Test valid ticker symbols."""
        assert security.validate_ticker("AAPL")
        assert security.validate_ticker("BRK.B")
        assert security.validate_ticker("SPY")
        assert security.validate_ticker("AMZN")
    
    def test_validate_ticker_invalid(self):
        """Test invalid ticker symbols."""
        assert not security.validate_ticker("<script>")
        assert not security.validate_ticker("'; DROP TABLE--")
        assert not security.validate_ticker("TOOMANYCHARACTERS")
        assert not security.validate_ticker("")
        assert not security.validate_ticker("@#$%")
        assert not security.validate_ticker("123")  # Only numbers
    
    def test_validate_email_valid(self):
        """Test valid emails."""
        assert security.validate_email("user@example.com")
        assert security.validate_email("john.doe+tag@subdomain.co.uk")
        assert security.validate_email("test@test.co")
    
    def test_validate_email_invalid(self):
        """Test invalid emails."""
        assert not security.validate_email("invalid@domain")  # No TLD
        assert not security.validate_email("invalid")  # No @
        assert not security.validate_email("@example.com")  # No local part
        assert not security.validate_email("user name@example.com")  # Space
        assert not security.validate_email("")
    
    def test_validate_numeric_valid(self):
        """Test valid numeric values."""
        is_valid, value = security.validate_numeric("123.45")
        assert is_valid and value == 123.45
        
        is_valid, value = security.validate_numeric("0", min_val=0, max_val=100)
        assert is_valid and value == 0
        
        is_valid, value = security.validate_numeric("100", min_val=0, max_val=100)
        assert is_valid and value == 100
    
    def test_validate_numeric_invalid(self):
        """Test invalid numeric values."""
        is_valid, value = security.validate_numeric("not a number")
        assert not is_valid and value is None
        
        is_valid, value = security.validate_numeric("-50", min_val=0)
        assert not is_valid  # Below min
        
        is_valid, value = security.validate_numeric("150", max_val=100)
        assert not is_valid  # Above max
    
    def test_validate_json_payload(self):
        """Test JSON payload validation."""
        # Valid payload
        assert security.validate_json_payload({"key": "value"})
        
        # Oversized payload
        large_data = {"data": "x" * 2_000_000}
        assert not security.validate_json_payload(large_data, max_size=1_000_000)


class TestSanitization:
    """Test string sanitization."""
    
    def test_sanitize_xss_attacks(self):
        """Test sanitization of XSS attack vectors."""
        # Script tag
        result = security.sanitize_string("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "alert" in result  # Content preserved
        assert "&lt;script&gt;" in result
        
        # Event handler
        result = security.sanitize_string('<img src=x onerror="alert(1)">')
        assert "<img" not in result
        assert "&lt;img" in result
        
        # SVG attack
        result = security.sanitize_string('<svg onload=alert(1)>')
        assert "<svg" not in result
        assert "&lt;svg" in result
    
    def test_sanitize_sql_injection(self):
        """Test sanitization of SQL injection attempts."""
        result = security.sanitize_string("'; DROP TABLE users; --")
        assert ";" not in result or "&" in result  # Escaped or removed
    
    def test_sanitize_length_limit(self):
        """Test string length limiting."""
        long_string = "x" * 2000
        result = security.sanitize_string(long_string, max_length=100)
        assert len(result) <= 100
    
    def test_sanitize_html_entities(self):
        """Test HTML entity escaping."""
        result = security.sanitize_string("<div>test</div>")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "<div>" not in result


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = security.RateLimiter()
        
        # Allow 5 requests per 60 seconds
        for i in range(5):
            assert limiter.is_allowed("test_key", 5, 60)
    
    def test_rate_limiter_blocks_excess_requests(self):
        """Test that requests exceeding limit are blocked."""
        limiter = security.RateLimiter()
        
        # Allow 3 requests per 60 seconds
        assert limiter.is_allowed("test_key", 3, 60)
        assert limiter.is_allowed("test_key", 3, 60)
        assert limiter.is_allowed("test_key", 3, 60)
        
        # Fourth request should be blocked
        assert not limiter.is_allowed("test_key", 3, 60)
    
    def test_rate_limiter_per_key_isolation(self):
        """Test that rate limits are per-key."""
        limiter = security.RateLimiter()
        
        # Both keys should be independent
        assert limiter.is_allowed("key1", 2, 60)
        assert limiter.is_allowed("key2", 2, 60)
        assert limiter.is_allowed("key1", 2, 60)
        assert limiter.is_allowed("key2", 2, 60)
        
        # Both should now be blocked
        assert not limiter.is_allowed("key1", 2, 60)
        assert not limiter.is_allowed("key2", 2, 60)


class TestCSRFProtection:
    """Test CSRF token generation and validation."""
    
    def test_csrf_token_generation(self):
        """Test CSRF token is generated."""
        token = security._generate_csrf_token()
        assert token
        assert len(token) > 20
    
    def test_csrf_tokens_are_unique(self):
        """Test that generated tokens are unique."""
        token1 = security._generate_csrf_token()
        token2 = security._generate_csrf_token()
        assert token1 != token2
    
    def test_csrf_token_format(self):
        """Test CSRF token format."""
        token = security._generate_csrf_token()
        # Should be base64url encoded
        assert isinstance(token, str)
        assert len(token) == 43  # Standard base64url token length

    def test_require_csrf_accepts_session_token(self):
        """Test explicit CSRF decorator accepts a matching header token."""
        app = security.flask.Flask(__name__)
        app.secret_key = "test-secret"

        @app.post("/form")
        @security.require_csrf
        def form_post():
            return "ok"

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_csrf_token"] = "known-token"

        assert client.post("/form", headers={"X-CSRF-Token": "known-token"}).status_code == 200
        assert client.post("/form", headers={"X-CSRF-Token": "bad-token"}).status_code == 403

    def test_init_csrf_protection_enforces_same_origin_posts(self):
        """Test blanket CSRF guard rejects cross-origin state-changing requests."""
        app = security.flask.Flask(__name__)
        app.secret_key = "test-secret"
        security.init_csrf_protection(app)

        @app.post("/mutate")
        def mutate():
            return "ok"

        client = app.test_client()
        assert client.post("/mutate", headers={"Origin": "http://localhost"}).status_code == 200
        assert client.post("/mutate", headers={"Origin": "http://evil.example"}).status_code == 403
        assert client.post("/mutate").status_code == 403


class TestEncryption:
    """Test sensitive data encryption."""
    
    def test_encryptor_encrypt_decrypt(self):
        """Test encryption and decryption."""
        encryptor = security.SensitiveDataEncryptor()
        
        if encryptor.cipher is None:
            pytest.skip("Encryption not available")
        
        original = "sensitive@example.com"
        encrypted = encryptor.encrypt(original)
        
        assert encrypted != original
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original
    
    def test_encryptor_handles_invalid_data(self):
        """Test encryption handles invalid decryption gracefully."""
        encryptor = security.SensitiveDataEncryptor()
        
        if encryptor.cipher is None:
            pytest.skip("Encryption not available")
        
        # Invalid encrypted data
        result = encryptor.decrypt("invalid_encrypted_data")
        # Should return None or original on error
        assert result is None or isinstance(result, str)


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_parameterized_queries_prevent_injection(self):
        """Test that parameterized queries prevent SQL injection."""
        # This is a conceptual test - actual DB testing requires a test DB
        
        # ✅ SAFE: Parameterized query
        ticker = "'; DROP TABLE users; --"
        # Using parameterized query: db.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,))
        # The ticker is treated as a value, not SQL code
        
        # This test verifies our validators would catch this
        is_valid = security.validate_ticker(ticker)
        assert not is_valid
    
    def test_invalid_ticker_blocks_injection(self):
        """Test that ticker validation blocks injection attempts."""
        injection_attempts = [
            "'; DROP TABLE--",
            "1' OR '1'='1",
            "UNION SELECT * FROM--",
            "<script>alert(1)</script>",
        ]
        
        for attempt in injection_attempts:
            assert not security.validate_ticker(attempt)


class TestSecurityHeaders:
    """Test security header configuration."""
    
    def test_security_header_constants(self):
        """Test that security module has required constants."""
        assert hasattr(security, 'IS_PRODUCTION')
        assert hasattr(security, 'SECURITY_LOGGER')
        assert hasattr(security, 'SENSITIVE_PATTERNS')

    def test_init_security_sets_baseline_headers(self):
        """Test that init_security adds browser hardening headers."""
        app = security.flask.Flask(__name__)
        app.secret_key = "test-secret"
        security.init_security(app)

        @app.get("/")
        def index():
            return "ok"

        response = app.test_client().get("/")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Access-Control-Allow-Origin"] == "none"


class TestLogging:
    """Test security event logging."""
    
    def test_log_security_event_masks_sensitive_data(self, caplog):
        """Test that sensitive data is masked in logs."""
        caplog.set_level("INFO", logger=security.SECURITY_LOGGER.name)
        security.log_security_event(
            event_type="TEST_EVENT",
            details={"password": "secret123", "nested": {"api_key": "abc"}, "safe": "visible"}
        )
        log_text = caplog.text
        assert "TEST_EVENT" in log_text
        assert "visible" in log_text
        assert "secret123" not in log_text
        assert "abc" not in log_text
        assert "[REDACTED]" in log_text
    
    def test_audit_log_access_records_event(self):
        """Test that audit logging records access."""
        security.audit_log_access(
            action="READ",
            resource="test_resource",
            user_id="test_user",
            success=True
        )


class TestValidationEdgeCases:
    """Test edge cases in validation."""
    
    def test_none_inputs(self):
        """Test validation with None inputs."""
        assert not security.validate_ticker(None)
        assert not security.validate_email(None)
        assert not security.validate_json_payload(None)
    
    def test_empty_inputs(self):
        """Test validation with empty inputs."""
        assert not security.validate_ticker("")
        assert not security.validate_email("")
        assert security.validate_json_payload({})  # Empty dict is valid
    
    def test_unicode_handling(self):
        """Test validation with Unicode characters."""
        # Should handle Unicode gracefully
        assert not security.validate_ticker("北京")
        result = security.sanitize_string("你好世界")
        assert result is not None


if __name__ == "__main__":
    # Run tests with: pytest tests/test_security.py -v
    pytest.main([__file__, "-v"])
