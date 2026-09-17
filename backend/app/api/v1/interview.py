"""面试路由：开始面试、SSE 流式作答、历史回放（M2 计划 §二 PR1/PR2/PR3）。

红线 1：注册前已 grep `interview.router`，仅在本文件定义，registry 统一挂载。
红线 7：SSE 事件协议 meta/chunk/score/next/error；评分 JSON 走独立 score 事件。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.common.exceptions import InterviewInvalidState
from app.models.user import User
from app.schemas.interview import StartInterviewRequest, StartInterviewResponse, SubmitAnswerRequest
from app.services.common.redis import InterviewLock
from app.services.interview.service import InterviewService, emitter

router = APIRouter()


@router.post("", status_code=201, response_model=StartInterviewResponse)
async def start_interview(
    payload: StartInterviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开始面试：简历 + 岗位配置 → 出题落库 → 返回首题。"""
    return await InterviewService.start(
        db,
        user_id=current_user.id,
        resume_id=payload.resume_id,
        config=payload.config,
    )


@router.post("/{interview_id}/answer", response_class=StreamingResponse)
async def submit_answer(
    interview_id: int,
    payload: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """SSE 流式作答：meta → chunk* → score → next；评分 JSON 独立事件下发。"""
    # 校验前置：404/403/409 以 JSON 返回，不破坏 SSE 流（规范 §6.3/§8.2）
    interview = await InterviewService.validate_submit(
        db, user_id=current_user.id, interview_id=interview_id, round_=payload.round
    )

    # 互斥锁：防同 interview_id 并发提交交错污染 messages 表（M2-PR3 FS-10）
    lock_key = f"interview:{interview_id}:lock"
    lock_token = uuid.uuid4().hex
    if not await InterviewLock.acquire(redis, lock_key, lock_token, ttl=60):
        raise InterviewInvalidState("面试作答进行中，请勿重复提交")

    async def event_stream():
        try:
            async for event in InterviewService.stream_answer(
                db, interview=interview, content=payload.content, round_=payload.round
            ):
                yield event
        finally:
            await InterviewLock.release(redis, lock_key, lock_token)

    return StreamingResponse(
        emitter.serialize(event_stream()),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关闭 Nginx 缓冲（红线 7 / 规范 §8.2）
            "Content-Type": "text/event-stream",
        },
    )


@router.get("/{interview_id}/messages")
async def get_messages(
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """历史回放：断线重连后按 (question_index, round) 恢复现场（规范 §8.2）。"""
    items = await InterviewService.get_messages(
        db, user_id=current_user.id, interview_id=interview_id
    )
    return {"items": [m.model_dump() for m in items]}
