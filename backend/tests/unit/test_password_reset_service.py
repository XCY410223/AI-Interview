"""忘记密码找回服务单测（§5）：防枚举 / 限流 / 单次 token / 全下线。"""
from __future__ import annotations

import asyncio

import pytest

from app.common.exceptions import AuthRateLimited, AuthResetTokenInvalid
from app.core.security import generate_reset_token, hash_password, hash_reset_token, verify_password
from app.services.auth.password_reset_service import PasswordResetService
from tests.fakes import FakeRedis, FakeSession, make_user


def run(coro):
    return asyncio.run(coro)


def _patch_enqueue(monkeypatch):
    calls: list[tuple[int, str]] = []

    def fake_enqueue(user_id: int, token: str) -> str:
        calls.append((user_id, token))
        return "task-1"

    monkeypatch.setattr(PasswordResetService, "_enqueue", staticmethod(fake_enqueue))
    return calls


def test_request_reset_existing_user_writes_token_and_enqueues(monkeypatch):
    calls = _patch_enqueue(monkeypatch)
    db = FakeSession().configure(scalar_one_or_none=make_user(user_id=7, email="a@b.com"))
    redis = FakeRedis()
    run(PasswordResetService.request_reset(db, redis, email="a@b.com", ip="1.2.3.4"))
    assert len(calls) == 1
    assert calls[0][0] == 7
    assert len(redis._data) == 1
    (key, value), = redis._data.items()
    assert key.startswith("pwd_reset:")
    assert value == "7"


def test_request_reset_unknown_email_silent_no_side_effect(monkeypatch):
    calls = _patch_enqueue(monkeypatch)
    db = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    run(PasswordResetService.request_reset(db, redis, email="nobody@x.com", ip="1.2.3.4"))
    assert calls == []
    assert redis._data == {}  # 不写 token、不发任务


def test_request_reset_email_rate_limited_after_3(monkeypatch):
    calls = _patch_enqueue(monkeypatch)
    db = FakeSession().configure(scalar_one_or_none=make_user())
    redis = FakeRedis()
    for _ in range(3):
        run(PasswordResetService.request_reset(db, redis, email="a@b.com", ip="1.2.3.4"))
    with pytest.raises(AuthRateLimited):
        run(PasswordResetService.request_reset(db, redis, email="a@b.com", ip="1.2.3.4"))
    assert len(calls) == 3


def test_request_reset_ip_rate_limited_after_10(monkeypatch):
    _patch_enqueue(monkeypatch)
    db = FakeSession().configure(scalar_one_or_none=make_user())
    redis = FakeRedis()
    for i in range(10):
        run(PasswordResetService.request_reset(db, redis, email=f"u{i}@x.com", ip="1.2.3.4"))
    with pytest.raises(AuthRateLimited):
        run(PasswordResetService.request_reset(db, redis, email="u10@x.com", ip="1.2.3.4"))


def test_validate_token_readonly():
    redis = FakeRedis()
    token = generate_reset_token()
    key = PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))
    redis._data[key] = "1"
    assert run(PasswordResetService.validate(redis, token)) is True
    assert redis._data[key] == "1"  # 只读，不消费
    assert run(PasswordResetService.validate(redis, "bogus-token")) is False


def test_reset_password_success_revokes_and_commits():
    user = make_user(user_id=1, password_hash=hash_password("old", cost=4))
    db = FakeSession().configure(get_map={1: user}, rowcount=1)
    redis = FakeRedis()
    token = generate_reset_token()
    redis._data[PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))] = "1"
    run(PasswordResetService.reset_password(db, redis, token=token, new_password="newpassword123"))
    assert verify_password("newpassword123", user.password_hash)
    assert redis._data == {}  # getdel 已消费
    assert any("refresh_tokens" in str(s) for s in db.executed)  # 撤销 refresh token
    assert db.committed


def test_reset_password_invalid_token_400():
    db = FakeSession().configure(get_map={1: make_user()})
    redis = FakeRedis()
    with pytest.raises(AuthResetTokenInvalid):
        run(PasswordResetService.reset_password(db, redis, token="x" * 43, new_password="newpassword123"))


def test_reset_password_token_single_use():
    user = make_user(user_id=1, password_hash=hash_password("old", cost=4))
    db = FakeSession().configure(get_map={1: user}, rowcount=1)
    redis = FakeRedis()
    token = generate_reset_token()
    redis._data[PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))] = "1"
    run(PasswordResetService.reset_password(db, redis, token=token, new_password="newpassword123"))
    with pytest.raises(AuthResetTokenInvalid):
        run(PasswordResetService.reset_password(db, redis, token=token, new_password="newpassword456"))
