"""core/rate_limit 单测：滑动窗口计数、不新增的 count、窗口外剔除。"""
from __future__ import annotations

import asyncio

from app.core.rate_limit import window_count, window_record
from tests.fakes import FakeRedis


def run(coro):
    return asyncio.run(coro)


def test_window_record_increments():
    redis = FakeRedis()
    assert run(window_record(redis, "k", 60)) == 1
    assert run(window_record(redis, "k", 60)) == 2


def test_window_count_does_not_record():
    redis = FakeRedis()
    run(window_record(redis, "k", 60))
    assert run(window_count(redis, "k", 60)) == 1
    assert run(window_count(redis, "k", 60)) == 1  # 不新增


def test_window_prunes_old_entries():
    redis = FakeRedis()
    run(window_record(redis, "k", 60))
    # 直接塞一个窗口外的旧 member（score=0）
    redis._zsets["k"]["old:member"] = 0.0
    assert run(window_count(redis, "k", 60)) == 1  # 旧 member 被剔除
