"""面试业务编排（M2-PR1/PR2）：start / submit_answer(SSE)。

分层约束（规范 §4）：本层负责业务编排、prompt 加载、SSE 事件组装、调 core/llm；
session 由 FastAPI Depends 注入，禁止自行 new session。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import InterviewForbidden, InterviewInvalidState, InterviewNotFound
from app.core.llm.client import LLMError
from app.models.interview import (
    INTERVIEW_STATUS_COMPLETED,
    INTERVIEW_STATUS_CREATED,
    INTERVIEW_STATUS_IN_PROGRESS,
    Interview,
)
from app.models.resume import Resume
from app.schemas.interview import InterviewConfig, QuestionItem, StartInterviewResponse
from app.schemas.interview_event import SSEEvent
from app.services.interview.ai_service import InterviewAIService
from app.services.interview.sse_emitter import SSEEmitter

logger = logging.getLogger(__name__)

_ESTIMATED_MINUTES_PER_QUESTION = 2

ai_service = InterviewAIService()
emitter = SSEEmitter()


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


def _get_question(interview: Interview, index: int) -> QuestionItem | None:
    questions = interview.questions_json or []
    if not isinstance(questions, list) or not (0 <= index < len(questions)):
        return None
    raw = questions[index]
    if not isinstance(raw, dict):
        return None
    try:
        return QuestionItem.model_validate(raw)
    except Exception:  # 快照损坏兜底，绝不 500（规范 §7.2）
        return None


class InterviewService:
    # ------------------------------------------------------------------
    # start：出题 + 建场次（M2-PR1）
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 提交回答前的校验（在路由层执行，错误以 JSON 返回，而非破坏 SSE 流）
    # ------------------------------------------------------------------
    @staticmethod
    async def validate_submit(
        db: AsyncSession,
        *,
        user_id: int,
        interview_id: int,
        round_: int,
    ) -> Interview:
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None:
            raise InterviewNotFound()
        if interview.user_id != user_id:
            raise InterviewForbidden()
        if interview.status == INTERVIEW_STATUS_COMPLETED:
            raise InterviewInvalidState("面试已结束")
        if round_ != interview.current_round:
            raise InterviewInvalidState(f"round 不匹配：期望 {interview.current_round}，实际 {round_}")
        return interview

    # ------------------------------------------------------------------
    # SSE 流式回答（M2-PR2）：meta → chunk* → score → next（线性推进）
    # ------------------------------------------------------------------
    @staticmethod
    async def stream_answer(
        db: AsyncSession,
        *,
        interview: Interview,
        content: str,
        round_: int,
    ) -> AsyncIterator[SSEEvent]:
        interview_id = interview.id
        question_index = interview.current_question_index
        question = _get_question(interview, question_index)
        if question is None:
            yield emitter.error("INVALID_STATE", "当前题目不存在")
            return

        yield emitter.meta(interview_id, question_index, round_)

        # 1) 评语流 → chunk 事件（流式失败 → error，不进入评分）
        try:
            async for delta in ai_service.stream_feedback(question=question, answer=content):
                yield emitter.chunk(delta)
        except LLMError as exc:
            logger.warning("评语流失败 interview_id=%s: %s", interview_id, exc)
            yield emitter.error("AI_TIMEOUT", "评语生成超时，请重试")
            return

        # 2) 评分结构化 → score 事件（内部已兜底，不抛）
        score_data = await ai_service.evaluate_score(question=question, answer=content)
        yield emitter.score(
            {
                "score": score_data.score,
                "dimensions": score_data.dimensions,
                "feedback": score_data.feedback,
                "follow_up_suggestion": False,
            }
        )

        # 3) 线性推进：下一题 / 结束（追问状态机在 M2-PR3 引入）
        next_index = question_index + 1
        nxt = _get_question(interview, next_index) if next_index < interview.question_count else None
        if nxt is None:
            yield emitter.next(None, None, None)
            interview.status = INTERVIEW_STATUS_COMPLETED
            interview.completed_at = datetime.now(timezone.utc)
        else:
            yield emitter.next(nxt.content, next_index, 0)
            interview.current_question_index = next_index
            interview.current_round = 0
            interview.status = INTERVIEW_STATUS_IN_PROGRESS

        await db.commit()


__all__ = ["InterviewService", "ai_service", "emitter"]
