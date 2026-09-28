"""AI 调用统一限流（规范 §9.1/§11.4）：复用 AI_RATE_LIMIT_PER_HOUR，按用户维度防刷。

JD 解析 / 真题重评 / 专项练习等交互式单次 LLM 调用，统一在此计费 + 限流（M4 计划 D1/D7）。
滑动窗口计数复用 core/rate_limit.window_record。
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.common.exceptions import AIRateLimited
from app.core.config import settings
from app.core.rate_limit import window_record

AI_RATE_WINDOW_SECONDS = 3600  # 1 小时窗口


def ai_rate_key(user_id: int) -> str:
    return f"rate:ai:{user_id}"


async def charge_ai_request(redis: Redis, user_id: int) -> None:
    """记录一次 AI 调用并校验限流；超限抛 AIRateLimited（429）。"""
    count = await window_record(redis, ai_rate_key(user_id), AI_RATE_WINDOW_SECONDS)
    if count > settings.AI_RATE_LIMIT_PER_HOUR:
        raise AIRateLimited()


__all__ = ["AI_RATE_WINDOW_SECONDS", "ai_rate_key", "charge_ai_request"]
