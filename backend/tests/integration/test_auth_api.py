"""账户 API 集成测试（TestClient + 内存 fakes，M1 计划 §3.5）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.security import create_access_token, create_refresh_token, hash_password, hash_refresh_token
from tests.fakes import make_user


def test_register_success(client):
    client.state["db"].configure(scalar_one_or_none=None)
    resp = client.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "a@b.com"
    assert data["access_token"] and data["refresh_token"]


def test_register_duplicate_email_409(client):
    client.state["db"].configure(scalar_one_or_none=make_user())
    resp = client.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "AUTH_EMAIL_TAKEN"


def test_register_weak_password_422(client):
    resp = client.post("/api/v1/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_login_success(client):
    hashed = hash_password("password123", cost=4)
    client.state["db"].configure(scalar_one_or_none=make_user(password_hash=hashed))
    resp = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_401(client):
    hashed = hash_password("correct", cost=4)
    client.state["db"].configure(scalar_one_or_none=make_user(password_hash=hashed))
    resp = client.post("/api/v1/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_login_nonexistent_email_same_401(client):
    client.state["db"].configure(scalar_one_or_none=None)
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@x.com", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_CREDENTIALS"


def test_refresh_success(client):
    refresh, jti = create_refresh_token(1)
    record = SimpleNamespace(
        id=1, user_id=1, token_hash=hash_refresh_token(jti),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1), revoked=False, replaced_by=None,
    )
    client.state["db"].configure(scalar_one_or_none=record)
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] and data["refresh_token"]


def test_refresh_reused_token_revokes_chain(client):
    refresh, jti = create_refresh_token(1)
    revoked = SimpleNamespace(
        id=1, user_id=1, token_hash=hash_refresh_token(jti),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1), revoked=True, replaced_by=2,
    )
    legit = SimpleNamespace(
        id=2, user_id=1, token_hash="other",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1), revoked=False, replaced_by=None,
    )
    client.state["db"].configure(scalar_one_or_none=revoked, get_map={2: legit})
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_TOKEN_REVOKED"
    assert legit.revoked is True


def test_logout_204_and_blacklists(client):
    refresh, jti = create_refresh_token(1)
    record = SimpleNamespace(
        id=1, user_id=1, token_hash=hash_refresh_token(jti),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1), revoked=False, replaced_by=None,
    )
    client.state["db"].configure(scalar_one_or_none=record)
    resp = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert resp.status_code == 204
    assert client.state["redis"]._data.get(f"blacklist:{jti}") == "1"


def test_me_with_valid_token(client):
    client.state["db"].configure(get_map={1: make_user(user_id=1)})
    token = create_access_token(1)
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "a@b.com"


def test_me_unauthorized(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
