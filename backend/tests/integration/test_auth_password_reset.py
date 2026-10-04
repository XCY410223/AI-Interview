"""忘记密码找回 API 集成测试（TestClient + 内存 fakes，§5）。"""
from __future__ import annotations

from app.core.security import generate_reset_token, hash_reset_token
from app.services.auth.password_reset_service import PasswordResetService
from tests.fakes import make_user

FORGOT_MSG = {"code": 0, "message": "如邮箱已注册，重置邮件已发送", "data": None}


def _seed_token(redis, user_id: int = 1, token: str | None = None) -> str:
    token = token or generate_reset_token()
    key = PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))
    redis._data[key] = str(user_id)
    return token


# ---- forgot-password ----

def test_forgot_password_unknown_email_same_response(client):
    client.state["db"].configure(scalar_one_or_none=None)
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@x.com"})
    assert resp.status_code == 200
    assert resp.json() == FORGOT_MSG  # 与注册邮箱完全一致（防枚举）


def test_forgot_password_existing_email_enqueues_once(client, monkeypatch):
    calls: list[tuple[int, str]] = []
    monkeypatch.setattr(
        PasswordResetService, "_enqueue",
        staticmethod(lambda user_id, token: calls.append((user_id, token))),
    )
    client.state["db"].configure(scalar_one_or_none=make_user(user_id=7, email="a@b.com"))
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "a@b.com"})
    assert resp.status_code == 200
    assert resp.json() == FORGOT_MSG
    assert len(calls) == 1
    assert calls[0][0] == 7


def test_forgot_password_email_rate_limited(client, monkeypatch):
    monkeypatch.setattr(PasswordResetService, "_enqueue", staticmethod(lambda user_id, token: "task"))
    client.state["db"].configure(scalar_one_or_none=make_user())
    for _ in range(3):
        assert client.post("/api/v1/auth/forgot-password", json={"email": "a@b.com"}).status_code == 200
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "a@b.com"})
    assert resp.status_code == 429
    assert resp.json()["code"] == "AUTH_RATE_LIMITED"


def test_forgot_password_ip_rate_limited(client, monkeypatch):
    monkeypatch.setattr(PasswordResetService, "_enqueue", staticmethod(lambda user_id, token: "task"))
    client.state["db"].configure(scalar_one_or_none=make_user())
    for i in range(10):
        assert client.post("/api/v1/auth/forgot-password", json={"email": f"u{i}@x.com"}).status_code == 200
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "u10@x.com"})
    assert resp.status_code == 429
    assert resp.json()["code"] == "AUTH_RATE_LIMITED"


def test_forgot_password_invalid_email_422(client):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


# ---- validate ----

def test_validate_valid_token(client):
    token = _seed_token(client.state["redis"])
    resp = client.get("/api/v1/auth/reset-password/validate", params={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"valid": True}


def test_validate_invalid_or_used_token(client):
    resp = client.get("/api/v1/auth/reset-password/validate", params={"token": "x" * 43})
    assert resp.status_code == 200
    assert resp.json() == {"valid": False}


# ---- reset-password ----

def test_reset_password_success_revokes_refresh_tokens(client):
    user = make_user(user_id=1, password_hash="old-hash")
    client.state["db"].configure(get_map={1: user}, rowcount=1)
    token = _seed_token(client.state["redis"])
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert resp.status_code == 200
    assert resp.json()["message"] == "密码已重置，请重新登录"
    assert client.state["redis"]._data == {}  # GETDEL 已消费
    # 全下线：撤销该用户 refresh token 的 UPDATE 已执行
    assert any("refresh_tokens" in str(s) for s in client.state["db"].executed)


def test_reset_password_token_single_use(client):
    client.state["db"].configure(get_map={1: make_user()}, rowcount=1)
    token = _seed_token(client.state["redis"])
    first = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert first.status_code == 200
    second = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword456"})
    assert second.status_code == 400
    assert second.json()["code"] == "AUTH_RESET_TOKEN_INVALID"


def test_reset_password_invalid_token_400(client):
    client.state["db"].configure(get_map={1: make_user()})
    resp = client.post("/api/v1/auth/reset-password", json={"token": "x" * 43, "new_password": "newpassword123"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "AUTH_RESET_TOKEN_INVALID"


def test_reset_password_weak_password_422(client):
    client.state["db"].configure(get_map={1: make_user()})
    token = _seed_token(client.state["redis"])
    resp = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_reset_password_empty_or_long_token_422(client):
    assert client.post(
        "/api/v1/auth/reset-password", json={"token": "", "new_password": "newpassword123"}
    ).status_code == 422
    assert client.post(
        "/api/v1/auth/reset-password", json={"token": "x" * 200, "new_password": "newpassword123"}
    ).status_code == 422
