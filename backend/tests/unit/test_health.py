"""health 单测：GET /health 返回静态状态。"""
import asyncio

from app.api.v1.health import health


def test_health_returns_ok():
    result = asyncio.run(health())
    assert result == {"status": "ok"}
