"""services/auth/token_service 单测：轮换/重放撤销整链/登出黑名单（M1 计划 §3.5）。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.common.exceptions import AuthInvalidCredentials, AuthTokenExpired, AuthTokenRevoked
from app.core.security import create_refresh_token, hash_refresh_token
from app.services.auth.token_service import TokenService
from tests.fakes import FakeRedis, FakeSession


def run(coro):
    return asyncio.run(coro)


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=1)


def _record(jti: str, *, revoked: bool = False, replaced_by: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=1, user_id=1, token_hash=hash_refresh_token(jti), expires_at=_future(),
        revoked=revoked, replaced_by=replaced_by, last_used_at=None,
    )


def test_issue_persists_refresh_record():
    db = FakeSession()
    tokens = run(TokenService.issue(db, 1))
    assert "access_token" in tokens and "refresh_token" in tokens
    assert len(db.added) == 1
    assert db.added[0].user_id == 1


def test_rotate_success_marks_old_revoked_and_links():
    refresh, jti = create_refresh_token(1)
    record = _record(jti)
    db = FakeSession().configure(scalar_one_or_none=record)
    redis = FakeRedis()
    tokens = run(TokenService.rotate(db, redis, refresh))
    assert "access_token" in tokens and "refresh_token" in tokens
    assert record.revoked is True
    assert record.replaced_by is not None  # 指向新 token
    assert db.committed


def test_rotate_revoked_token_revokes_chain():
    refresh, jti = create_refresh_token(1)
    revoked_record = _record(jti, revoked=True, replaced_by=2)
    legit_record = SimpleNamespace(
        id=2, user_id=1, token_hash="other", expires_at=_future(), revoked=False, replaced_by=None,
    )
    db = FakeSession().configure(scalar_one_or_none=revoked_record, get_map={2: legit_record})
    redis = FakeRedis()
    with pytest.raises(AuthTokenRevoked):
        run(TokenService.rotate(db, redis, refresh))
    assert legit_record.revoked is True  # 整链撤销


def test_rotate_expired_token_401():
    refresh, jti = create_refresh_token(1)
    record = SimpleNamespace(
        id=1, user_id=1, token_hash=hash_refresh_token(jti),
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=10), revoked=False, replaced_by=None,
    )
    db = FakeSession().configure(scalar_one_or_none=record)
    with pytest.raises(AuthTokenExpired):
        run(TokenService.rotate(db, None, refresh))


def test_rotate_unknown_token_401():
    refresh, _ = create_refresh_token(1)
    db = FakeSession().configure(scalar_one_or_none=None)
    with pytest.raises(AuthInvalidCredentials):
        run(TokenService.rotate(db, None, refresh))


def test_logout_revokes_and_blacklists():
    refresh, jti = create_refresh_token(1)
    record = _record(jti)
    db = FakeSession().configure(scalar_one_or_none=record)
    redis = FakeRedis()
    run(TokenService.revoke(db, redis, refresh))
    assert record.revoked is True
    assert redis._data.get(f"blacklist:{jti}") == "1"


def test_rotate_blacklisted_token_401():
    refresh, jti = create_refresh_token(1)
    record = _record(jti)
    db = FakeSession().configure(scalar_one_or_none=record)
    redis = FakeRedis()
    redis._data[f"blacklist:{jti}"] = "1"
    with pytest.raises(AuthTokenRevoked):
        run(TokenService.rotate(db, redis, refresh))


def test_revoke_all_for_user_returns_rowcount_and_targets_user():
    db = FakeSession().configure(rowcount=2)
    assert run(TokenService.revoke_all_for_user(db, 42)) == 2
    assert len(db.executed) == 1
    sql = str(db.executed[0])
    assert "refresh_tokens" in sql
    assert "user_id" in sql  # 仅按目标用户过滤
