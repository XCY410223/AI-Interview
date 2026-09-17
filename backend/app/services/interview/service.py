"""面试业务编排（M2-PR1）：start 出题 + 建场次。

分层约束（规范 §4）：本层负责业务编排、prompt 加载、调 core/llm；
session 由 FastAPI Depends 注入，禁止自行 new session。
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import InterviewForbidden
from app.models.interview import INTERVIEW_STATUS_CREATED, Interview
from app.models.resume import Resume
from app.schemas.interview import InterviewConfig, StartInterviewResponse
from app.services.interview.ai_service import InterviewAIService

logger = logging.getLogger(__name__)

_ESTIMATED_MINUTES_PER_QUESTION = 2

ai_service = InterviewAIService()


def _resume_summary(resume: Resume | None) -> str:
    """从解析结果抽取摘要；未解析/空则返回空串（出通用题）。"""
    parsed = getattr(resume, "parsed_content", None) or {}
    if not isinstance(parsed, dict):
        return ""
    summary = parsed.get("summary") or ""
    if summary:
        return summary
    parts: list[str] = []
    skills = parsed.get("skills") or []
    if skills:
        parts.append("技能：" + "、".join(skills))
    for project in (parsed.get("projects") or [])[:3]:
        if isinstance(project, dict) and project.get("name"):
            parts.append(f"项目：{project['name']}")
    return "；".join(parts)


class InterviewService:
    @staticmethod
    async def start(
        db: AsyncSession,
        *,
        user_id: int,
        resume_id: int,
        config: InterviewConfig,
    ) -> StartInterviewResponse:
        resume = await db.get(Resume, resume_id)
        if resume is not None and resume.deleted_at is None:
            if resume.user_id != user_id:
                raise InterviewForbidden()  # 归属校验（§11.3）
            summary = _resume_summary(resume)
        else:
            summary = ""  # 简历缺失/软删：兜底通用题（QG-02）

        questions = await ai_service.generate_questions(
            position=config.position,
            difficulty=config.difficulty,
            resume_summary=summary,
            question_count=config.question_count,
        )
        interview = Interview(
            user_id=user_id,
            resume_id=resume_id,
            position=config.position,
            difficulty=config.difficulty,
            question_count=config.question_count,
            style=config.style,
            status=INTERVIEW_STATUS_CREATED,
            current_question_index=0,
            current_round=0,
            questions_json=[q.model_dump() for q in questions],
            config_json=config.model_dump(),
        )
        db.add(interview)
        await db.commit()
        await db.refresh(interview)
        logger.info(
            "interview started user_id=%s interview_id=%s style=%s count=%s",
            user_id, interview.id, config.style, len(questions),
        )
        return StartInterviewResponse(
            interview_id=interview.id,
            total_questions=len(questions),
            first_question=questions[0],
            estimated_minutes=len(questions) * _ESTIMATED_MINUTES_PER_QUESTION,
        )


__all__ = ["InterviewService", "ai_service"]
