import base64

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from codes import auth


def _b64url(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _rsa_jwk(public_key, kid="test-key"):
    numbers = public_key.public_numbers()
    return {"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256", "n": _b64url(numbers.n), "e": _b64url(numbers.e)}


def test_jwks_decode_accepts_only_matching_rs256_token(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {"keys": [_rsa_jwk(private_key.public_key())]}
    monkeypatch.setattr(auth, "_fetch_jwks", lambda _url: jwks)
    claims = {"sub": "user-123", "iss": "https://issuer.example/", "aud": "factorresearch"}

    valid = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})
    invalid = jwt.encode(claims, "not-the-rsa-key" * 3, algorithm="HS256", headers={"kid": "test-key"})

    assert auth._decode_jwt(valid, "https://issuer.example/jwks", "factorresearch", "https://issuer.example/") == claims
    assert auth._decode_jwt(invalid, "https://issuer.example/jwks", "factorresearch", "https://issuer.example/") is None
