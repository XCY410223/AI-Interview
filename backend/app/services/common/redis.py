"""Redis 服务：面试作答互斥锁（M2-PR3 FS-10）。

用 SET NX EX 实现轻量分布式锁，release 时做 token 比对，仅释放自己持有的锁。
"""
from __future__ import annotations

from redis.asyncio import Redis


class InterviewLock:
    """面试场次互斥锁：防止同 interview_id 并发提交交错污染 messages 表。"""

    @staticmethod
    async def acquire(redis: Redis, key: str, token: str, ttl: int = 60) -> bool:
        return bool(await redis.set(key, token, nx=True, ex=ttl))

    @staticmethod
    async def release(redis: Redis, key: str, token: str) -> None:
        current = await redis.get(key)
        if current == token:
            await redis.delete(key)


__all__ = ["InterviewLock"]
