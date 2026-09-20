"""报告 Redis 缓存（M3 计划 §六）：生成幂等锁 + 结果缓存。

三层职责：
① 生成幂等锁 report:gen_lock:{interview_id} —— 防并发/连点触发重复计费；
② 结果缓存 report:payload:{user_id}:{report_id} —— GET 高频读取不打 DB（key 含 user_id 防越权，§11.3）；
③ 产物复用 reports.pdf_object_key —— PDF 只渲染一次（对象存储，任务内处理）。
"""
from __future__ import annotations

import json

from redis.asyncio import Redis

GEN_LOCK_TTL = 300
PAYLOAD_TTL = 86400


def gen_lock_key(interview_id: int) -> str:
    return f"report:gen_lock:{interview_id}"


def payload_key(user_id: int, report_id: int) -> str:
    return f"report:payload:{user_id}:{report_id}"


async def acquire_gen_lock(redis: Redis, interview_id: int) -> bool:
    """生成幂等锁：SET key 1 NX EX 300。拿不到说明已有生成在进行。"""
    return bool(await redis.set(gen_lock_key(interview_id), "1", nx=True, ex=GEN_LOCK_TTL))


async def release_gen_lock(redis: Redis, interview_id: int) -> None:
    await redis.delete(gen_lock_key(interview_id))


async def get_payload(redis: Redis, user_id: int, report_id: int) -> dict | None:
    raw = await redis.get(payload_key(user_id, report_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


async def set_payload(redis: Redis, user_id: int, report_id: int, detail: dict) -> None:
    await redis.set(payload_key(user_id, report_id), json.dumps(detail, ensure_ascii=False), ex=PAYLOAD_TTL)


async def invalidate_payload(redis: Redis, user_id: int, report_id: int) -> None:
    await redis.delete(payload_key(user_id, report_id))
