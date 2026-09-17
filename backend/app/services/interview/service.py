"""面试业务编排（M2-PR1/PR2/PR3）：start / submit_answer(SSE) / get_messages。

分层约束（规范 §4）：本层负责业务编排、状态机、prompt 加载、SSE 事件组装、调 core/llm；
session 由 FastAPI Depends 注入，禁止自行 new session。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import InterviewForbidden, InterviewInvalidState, InterviewNotFound
from app.core.llm.client import LLMError
from app.models.interview import (
    INTERVIEW_STATUS_COMPLETED,
    INTERVIEW_STATUS_CREATED,
    INTERVIEW_STATUS_IN_PROGRESS,
    Interview,
)
from app.models.interview_message import ROLE_CANDIDATE, ROLE_INTERVIEWER, InterviewMessage
from app.models.resume import Resume
from app.schemas.interview import InterviewConfig, QuestionItem, StartInterviewResponse
from app.schemas.interview_event import SSEEvent
from app.schemas.interview_message import InterviewMessageOut
from app.services.interview.ai_service import InterviewAIService
from app.services.interview.sse_emitter import SSEEmitter
from app.services.interview.state_machine import NextAction, decide_next
from app.services.interview.style_resolver import resolve_style

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


def _advance_state(interview: Interview, action: NextAction) -> None:
    interview.current_question_index = action.question_index
    interview.current_round = action.round
    interview.status = INTERVIEW_STATUS_IN_PROGRESS


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
    # SSE 流式回答（M2-PR2/PR3）：meta → chunk* → score → next（含追问状态机）
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
        style = resolve_style(interview.style)
        question = _get_question(interview, question_index)
        if question is None:
            yield emitter.error("INVALID_STATE", "当前题目不存在")
            return

        # 记录候选人回答
        db.add(
            InterviewMessage(
                interview_id=interview_id,
                question_index=question_index,
                round=round_,
                role=ROLE_CANDIDATE,
                content=content,
                event_type="answer",
            )
        )
        yield emitter.meta(interview_id, question_index, round_)

        # 1) 评语流 → chunk 事件（流式失败 → error，不进入评分）
        try:
            async for delta in ai_service.stream_feedback(question=question, answer=content, style=style):
                yield emitter.chunk(delta)
        except LLMError as exc:
            logger.warning("评语流失败 interview_id=%s: %s", interview_id, exc)
            yield emitter.error("AI_TIMEOUT", "评语生成超时，请重试")
            return

        # 2) 评分结构化 → score 事件（内部已兜底，不抛）
        score_data = await ai_service.evaluate_score(question=question, answer=content)

        # 3) 追问决策（基于前几轮历史，内部已兜底，不抛）
        history = await _answer_history(db, interview_id, question_index, before_round=round_)
        followup = await ai_service.decide_follow_up(
            question=question, answer_history=history, current_round=round_, style=style
        )

        # 4) 状态机推进
        action = decide_next(
            question_index=question_index,
            round_=round_,
            need_follow_up=followup.need_follow_up,
            score=score_data.score,
            total_questions=interview.question_count,
        )

        yield emitter.score(
            {
                "score": score_data.score,
                "dimensions": score_data.dimensions,
                "feedback": score_data.feedback,
                "follow_up_suggestion": followup.need_follow_up,
            }
        )
        db.add(
            InterviewMessage(
                interview_id=interview_id,
                question_index=question_index,
                round=round_,
                role=ROLE_INTERVIEWER,
                content=score_data.feedback,
                event_type="score",
                payload_json={"score": score_data.score, "dimensions": score_data.dimensions},
            )
        )

        if action.kind == "follow_up":
            next_q = followup.follow_up_hint or "请进一步补充说明。"
            yield emitter.next(next_q, question_index, action.round)
            _advance_state(interview, action)
            db.add(
                InterviewMessage(
                    interview_id=interview_id,
                    question_index=question_index,
                    round=action.round,
                    role=ROLE_INTERVIEWER,
                    content=next_q,
                    event_type="next",
                    payload_json={"need_follow_up": True, "reason": followup.reason},
                )
            )
        elif action.kind == "next_question":
            nxt = _get_question(interview, action.question_index)
            next_content = nxt.content if nxt else None
            yield emitter.next(next_content, action.question_index, action.round)
            _advance_state(interview, action)
            db.add(
                InterviewMessage(
                    interview_id=interview_id,
                    question_index=question_index,
                    round=round_,
                    role=ROLE_INTERVIEWER,
                    content=next_content or "",
                    event_type="next",
                    payload_json={"next_question_index": action.question_index},
                )
            )
        else:  # done（INTERVIEW_DONE）
            yield emitter.next(None, None, None)
            interview.status = INTERVIEW_STATUS_COMPLETED
            interview.completed_at = datetime.now(timezone.utc)
            db.add(
                InterviewMessage(
                    interview_id=interview_id,
                    question_index=question_index,
                    round=round_,
                    role=ROLE_INTERVIEWER,
                    content="面试结束",
                    event_type="next",
                    payload_json={"done": True},
                )
            )

        await db.commit()

    # ------------------------------------------------------------------
    # 历史回放（M2-PR3 FS-06，规范 §8.2 断线重连）
    # ------------------------------------------------------------------
    @staticmethod
    async def get_messages(
        db: AsyncSession,
        *,
        user_id: int,
        interview_id: int,
    ) -> list[InterviewMessageOut]:
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None:
            raise InterviewNotFound()
        if interview.user_id != user_id:
            raise InterviewForbidden()
        stmt = (
            select(InterviewMessage)
            .where(
                InterviewMessage.interview_id == interview_id,
                InterviewMessage.deleted_at.is_(None),
            )
            .order_by(
                InterviewMessage.question_index.asc(),
                InterviewMessage.round.asc(),
                InterviewMessage.id.asc(),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [InterviewMessageOut.model_validate(m) for m in rows]


async def _answer_history(
    db: AsyncSession,
    interview_id: int,
    question_index: int,
    before_round: int,
) -> list[str]:
    """当前题前几轮候选人回答（round < before_round，供追问决策）。"""
    stmt = (
        select(InterviewMessage)
        .where(
            InterviewMessage.interview_id == interview_id,
            InterviewMessage.question_index == question_index,
            InterviewMessage.role == ROLE_CANDIDATE,
            InterviewMessage.round < before_round,
            InterviewMessage.deleted_at.is_(None),
        )
        .order_by(InterviewMessage.round.asc(), InterviewMessage.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [m.content or "" for m in rows]


__all__ = ["InterviewService", "ai_service", "emitter"]
