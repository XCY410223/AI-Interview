"""Waiting List 服务单测（M4 PR-R7-d）：防重幂等 / 防刷限流 / 列表。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.common.exceptions import WaitingListRateLimited
from app.services.waiting_list.service import SUBSCRIBE_IP_LIMIT, WaitingListService
from tests.fakes import FakeRedis, FakeSession


def run(coro):
    return asyncio.run(coro)


def _entry(email="a@b.com"):
    return SimpleNamespace(id=1, email=email, created_at=None, deleted_at=None)


def test_subscribe_new(monkeypatch):
    session = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    monkeypatch.setattr("app.services.waiting_list.service.WaitingListService.enqueue", staticmethod(lambda email: "task-1"))
    entry, already = run(WaitingListService.subscribe(session, redis, email="a@b.com", ip="1.2.3.4"))
    assert already is False
    assert entry.email == "a@b.com"
    assert len(session.added) == 1


def test_subscribe_duplicate_idempotent(monkeypatch):
    monkeypatch.setattr("app.services.waiting_list.service.WaitingListService.enqueue", staticmethod(lambda email: "task-1"))
    existing = _entry("a@b.com")
    session = FakeSession().configure(scalar_one_or_none=existing)
    redis = FakeRedis()
    entry, already = run(WaitingListService.subscribe(session, redis, email="a@b.com", ip="1.2.3.4"))
    assert already is True
    assert len(session.added) == 0  # 不重复建行


def test_subscribe_rate_limited(monkeypatch):
    monkeypatch.setattr("app.services.waiting_list.service.WaitingListService.enqueue", staticmethod(lambda email: "task-1"))
    session = FakeSession().configure(scalar_one_or_none=None)
    redis = FakeRedis()
    # 超过每小时 5 次后触发 429
    for i in range(SUBSCRIBE_IP_LIMIT):
        run(WaitingListService.subscribe(session, redis, email=f"u{i}@b.com", ip="1.2.3.4"))
    with pytest.raises(WaitingListRateLimited):
        run(WaitingListService.subscribe(session, redis, email="x@b.com", ip="1.2.3.4"))


def test_list_all():
    e1 = _entry("a@b.com")
    e2 = _entry("c@d.com")
    session = FakeSession().configure(scalars=[e1, e2])
    items = run(WaitingListService.list_all(session))
    assert [i.email for i in items] == ["a@b.com", "c@d.com"]
