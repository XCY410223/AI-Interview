"""Waiting List 服务（M4 PR-R7-d）：公开订阅（邮箱唯一防重 + IP 限流防刷）+ CSV 导出。

分层约束（规范 §4）：session 由 FastAPI Depends 注入；确认信走 Celery（best-effort）。
"""
from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import WaitingListRateLimited
from app.core.rate_limit import window_record
from app.models.waiting_list import WaitingList

logger = logging.getLogger(__name__)

SUBSCRIBE_IP_LIMIT = 5   # 同一 IP 每小时 5 次（防刷）
WINDOW_HOUR = 3600


class WaitingListService:
    @staticmethod
    async def _get_by_email(db: AsyncSession, email: str) -> WaitingList | None:
        result = await db.execute(
            select(WaitingList).where(WaitingList.email == email, WaitingList.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def subscribe(db: AsyncSession, redis: Redis, *, email: str, ip: str) -> tuple[WaitingList, bool]:
        """订阅：IP 限流（防刷）→ 邮箱唯一（防重，幂等）。返回 (entry, already_subscribed)。"""
        ip_key = f"rate:waiting_list:ip:{ip}"
        if await window_record(redis, ip_key, WINDOW_HOUR) > SUBSCRIBE_IP_LIMIT:
            raise WaitingListRateLimited()

        existing = await WaitingListService._get_by_email(db, email)
        if existing is not None:
            return existing, True

        entry = WaitingList(email=email)
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        try:
            WaitingListService.enqueue(email)
        except Exception:  # 邮件投递失败不影响订阅（best-effort）
            logger.warning("waiting list confirmation enqueue failed email=%s", email)
        return entry, False

    @staticmethod
    def enqueue(email: str) -> str:
        """下发确认信任务（延迟导入避免循环依赖）。"""
        from app.tasks.email import send_waiting_list_confirmation

        result = send_waiting_list_confirmation.delay(email=email)
        return str(getattr(result, "id", "") or "")

    @staticmethod
    async def list_all(db: AsyncSession) -> list[WaitingList]:
        """导出用：全部有效订阅（按 id 升序）。"""
        stmt = (
            select(WaitingList)
            .where(WaitingList.deleted_at.is_(None))
            .order_by(WaitingList.id.asc())
        )
        return list((await db.execute(stmt)).scalars().all())


__all__ = ["WaitingListService", "SUBSCRIBE_IP_LIMIT", "WINDOW_HOUR"]
