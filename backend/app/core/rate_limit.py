"""滑动窗口限流（规范 §11.4）：登录/注册按 IP + 账号双重限流，防爆破。

基于 Redis ZSET 实现滑动窗口：每个请求时间戳作为一个 member，
窗口内计数，超限则拒绝。redis 参数可注入 fake 以便单测（不依赖真实 Redis）。
"""
from __future__ import annotations

import time
import uuid

from redis.asyncio import Redis


async def _prune(redis: Redis, key: str, window_seconds: int) -> None:
    """剔除窗口外的旧时间戳。"""
    cutoff = time.time() - window_seconds
    await redis.zremrangebyscore(key, 0, cutoff)


async def window_count(redis: Redis, key: str, window_seconds: int) -> int:
    """窗口内现有计数（不新增；用于「先查后放行」的账号级限流）。"""
    await _prune(redis, key, window_seconds)
    return int(await redis.zcard(key))


async def window_record(redis: Redis, key: str, window_seconds: int) -> int:
    """记录一次请求并返回窗口内计数（用于「每请求计数」的 IP 级限流）。"""
    now = time.time()
    await _prune(redis, key, window_seconds)
    # 唯一 member，避免同一时刻多请求塌缩
    member = f"{now:.6f}:{uuid.uuid4().hex}"
    await redis.zadd(key, {member: now})
    await redis.expire(key, window_seconds)
    return int(await redis.zcard(key))
