"""Waiting List 路由（M4 PR-R7-d）：公开订阅 + 管理侧 CSV 导出。

红线 1：注册前已 grep，仅在本文件定义，registry 统一挂载 `/waiting-list`。
红线 8：CSV 导出走 StreamingResponse 流式，不写本地磁盘。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.waiting_list import WaitingListSubscribeRequest, WaitingListSubscribeResponse
from app.services.waiting_list.service import WaitingListService

router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("", status_code=201, response_model=WaitingListSubscribeResponse)
async def subscribe(
    payload: WaitingListSubscribeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """公开订阅：邮箱校验 + IP 限流防刷 + 邮箱唯一防重（幂等）。"""
    entry, already = await WaitingListService.subscribe(
        db, redis, email=payload.email, ip=_client_ip(request)
    )
    return WaitingListSubscribeResponse(email=entry.email, already_subscribed=already)


@router.get("/export")
async def export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理侧 CSV 导出（流式，不落盘）。MVP 无角色系统，暂以登录态为门槛。"""
    entries = await WaitingListService.list_all(db)

    async def gen():
        yield "email,created_at\n"
        for e in entries:
            created = e.created_at.isoformat() if getattr(e, "created_at", None) else ""
            yield f"{e.email},{created}\n"

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waiting_list.csv"'},
    )


__all__ = ["router"]
