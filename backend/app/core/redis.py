"""Redis 客户端封装（规范 §3.3/§11.4）：缓存 / 限流 / refresh 黑名单。

使用 redis.asyncio 异步客户端；通过 FastAPI `Depends` 提供（见 api/v1/deps.py）。
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings


def build_redis() -> Redis:
    """构造 Redis 异步客户端（decode_responses，便于限流/黑名单计数）。"""
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
