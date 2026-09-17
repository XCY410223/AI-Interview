"""面试路由：开始面试（M2 计划 §二 PR1）。

红线 1：注册前已 grep `interview.router`，仅在本文件定义，registry 统一挂载。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.interview import StartInterviewRequest, StartInterviewResponse
from app.services.interview.service import InterviewService

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
