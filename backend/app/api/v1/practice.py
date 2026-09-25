"""弱项专项练习路由（M4 PR-R7-c）：生成 + 查询。

红线 1：注册前已 grep，仅在本文件定义，registry 统一挂载 `/practice`。
计入 AI 限流（生成练习题是一次额外 LLM 调用）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.interview import QuestionItem
from app.schemas.practice import PracticeCreateRequest, PracticeResponse
from app.services.common.ai_rate_limit import charge_ai_request
from app.services.practice.service import PracticeService

router = APIRouter()


@router.post("", status_code=201, response_model=PracticeResponse)
async def create_practice(
    payload: PracticeCreateRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """生成专项练习：报告弱项 → 针对性题目包（复用出题通道）。"""
    await charge_ai_request(redis, current_user.id)
    pack = await PracticeService.create(
        db, user_id=current_user.id, report_id=payload.report_id, count=payload.count
    )
    questions = [
        QuestionItem.model_validate(q) for q in (pack.questions_json or []) if isinstance(q, dict)
    ]
    return PracticeResponse(
        practice_id=pack.id, report_id=pack.report_id, count=pack.count, questions=questions
    )


@router.get("/{practice_id}", response_model=PracticeResponse)
async def get_practice(
    practice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询练习包（归属校验）。"""
    pack = await PracticeService.get(db, user_id=current_user.id, practice_id=practice_id)
    questions = [
        QuestionItem.model_validate(q) for q in (pack.questions_json or []) if isinstance(q, dict)
    ]
    return PracticeResponse(
        practice_id=pack.id, report_id=pack.report_id, count=pack.count, questions=questions
    )


__all__ = ["router"]
