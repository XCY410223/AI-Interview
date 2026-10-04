"""core/security 单测：bcrypt 成本/校验、JWT 编解码/过期、refresh jti、存根 hash。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    hash_password,
    hash_refresh_token,
    hash_reset_token,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    hashed = hash_password("secret123", cost=4)
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_default_cost_is_12():
    hashed = hash_password("secret123")  # 默认 cost=12
    assert hashed.split("$")[2] == "12"


def test_verify_invalid_hash_returns_false():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_access_token_roundtrip():
    token = create_access_token(42)
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_access_token_expired():
    payload = {
        "sub": "1",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=10),
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token, expected_type="access")


def test_decode_wrong_type_rejected():
    token = create_access_token(1)
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(token, expected_type="refresh")


def test_decode_tampered_token_rejected():
    token = create_access_token(1)
    # 篡改中间字符（末位 base64url 可能含未用位，篡改末位有歧义会偶发通过，故取中点）
    mid = len(token) // 2
    tampered = token[:mid] + ("a" if token[mid] != "a" else "b") + token[mid + 1:]
    with pytest.raises(pyjwt.PyJWTError):
        decode_token(tampered, expected_type="access")


def test_refresh_token_carries_jti():
    token, jti = create_refresh_token(7)
    payload = decode_token(token, expected_type="refresh")
    assert payload["jti"] == jti
    assert payload["sub"] == "7"


def test_hash_refresh_token_stable_and_distinct():
    assert hash_refresh_token("abc") == hash_refresh_token("abc")
    assert hash_refresh_token("abc") != hash_refresh_token("abd")


def test_generate_reset_token_high_entropy_and_distinct():
    t1 = generate_reset_token()
    t2 = generate_reset_token()
    assert t1 != t2
    assert len(t1) == 43  # token_urlsafe(32) → 43 字符
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    assert set(t1) <= allowed


def test_hash_reset_token_stable_and_distinct():
    assert hash_reset_token("abc") == hash_reset_token("abc")
    assert hash_reset_token("abc") != hash_reset_token("abd")
