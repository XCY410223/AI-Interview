"""services/auth/service 单测：注册/登录/双重限流（M1 计划 §3.5）。"""
from __future__ import annotations

import asyncio

import pytest

from app.common.exceptions import AuthEmailTaken, AuthInvalidCredentials, AuthRateLimited
from app.core.security import hash_password
from app.services.auth.service import AuthService
from tests.fakes import FakeRedis, FakeSession, make_user


def run(coro):
    return asyncio.run(coro)


def test_register_success_hashes_password_and_issues_tokens():
    db = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    user, tokens = run(
        AuthService.register(db, redis, email="a@b.com", password="password123", ip="1.2.3.4")
    )
    assert user.email == "a@b.com"
    assert user.id == 1  # flush 分配 id
    assert user.password_hash != "password123"
    assert "access_token" in tokens and "refresh_token" in tokens
    assert db.committed


def test_register_duplicate_email_409():
    db = FakeSession().configure(scalar_one_or_none=make_user())
    redis = FakeRedis()
    with pytest.raises(AuthEmailTaken):
        run(AuthService.register(db, redis, email="a@b.com", password="password123", ip="1.2.3.4"))


def test_register_rate_limited_after_5_per_ip():
    db = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    for i in range(5):
        run(AuthService.register(db, redis, email=f"u{i}@x.com", password="password123", ip="1.2.3.4"))
    with pytest.raises(AuthRateLimited):
        run(AuthService.register(db, redis, email="u6@x.com", password="password123", ip="1.2.3.4"))


def test_login_success_updates_last_login():
    hashed = hash_password("password123", cost=4)
    db = FakeSession().configure(scalar_one_or_none=make_user(password_hash=hashed))
    redis = FakeRedis()
    user, tokens = run(AuthService.login(db, redis, email="a@b.com", password="password123", ip="1.2.3.4"))
    assert user.last_login_at is not None
    assert "access_token" in tokens and "refresh_token" in tokens


def test_login_wrong_password_401():
    hashed = hash_password("correct", cost=4)
    db = FakeSession().configure(scalar_one_or_none=make_user(password_hash=hashed))
    redis = FakeRedis()
    with pytest.raises(AuthInvalidCredentials):
        run(AuthService.login(db, redis, email="a@b.com", password="wrong", ip="1.2.3.4"))


def test_login_nonexistent_email_same_error():
    db = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    with pytest.raises(AuthInvalidCredentials):
        run(AuthService.login(db, redis, email="nobody@x.com", password="x", ip="1.2.3.4"))


def test_login_email_rate_limited_after_5_failures():
    db = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    for _ in range(5):
        with pytest.raises(AuthInvalidCredentials):
            run(AuthService.login(db, redis, email="nobody@x.com", password="x", ip="1.2.3.4"))
    with pytest.raises(AuthRateLimited):
        run(AuthService.login(db, redis, email="nobody@x.com", password="x", ip="1.2.3.4"))
