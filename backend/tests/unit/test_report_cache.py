"""报告缓存单测：key 拼装、锁 SET NX、payload 往返、越权隔离（M3 计划 §六/§十一）。"""
from __future__ import annotations

import asyncio

from app.services.report.cache import (
    acquire_gen_lock,
    gen_lock_key,
    get_payload,
    payload_key,
    release_gen_lock,
    set_payload,
)
from tests.fakes import FakeRedis


def run(coro):
    return asyncio.run(coro)


def test_key_format():
    assert gen_lock_key(7) == "report:gen_lock:7"
    # key 含 user_id，防越权读取（§11.3）
    assert payload_key(2, 3) == "report:payload:2:3"


def test_gen_lock_exclusive():
    redis = FakeRedis()
    assert run(acquire_gen_lock(redis, 1)) is True
    assert run(acquire_gen_lock(redis, 1)) is False  # 已持有
    run(release_gen_lock(redis, 1))
    assert run(acquire_gen_lock(redis, 1)) is True  # 释放后可再拿


def test_payload_roundtrip_and_ownership_isolation():
    redis = FakeRedis()
    run(set_payload(redis, 2, 3, {"status": "completed", "overall_score": 8.5}))
    assert run(get_payload(redis, 2, 3)) == {"status": "completed", "overall_score": 8.5}
    assert run(get_payload(redis, 9, 3)) is None  # 不同 user 读不到
