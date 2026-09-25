"""面试业务编排（M2-PR1/PR2/PR3）：start / submit_answer(SSE) / get_messages。

分层约束（规范 §4）：本层负责业务编排、状态机、prompt 加载、SSE 事件组装、调 core/llm；
session 由 FastAPI Depends 注入，禁止自行 new session。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import InterviewForbidden, InterviewInvalidState, InterviewNotFound
from app.common.pagination import parse_pagination
from app.core.llm.client import LLMError
from app.models.interview import (
    INTERVIEW_STATUS_COMPLETED,
    INTERVIEW_STATUS_CREATED,
    INTERVIEW_STATUS_IN_PROGRESS,
    Interview,
)
from app.models.interview_message import ROLE_CANDIDATE, ROLE_INTERVIEWER, InterviewMessage
from app.models.resume import Resume
from app.prompts.report import CURRENT_VERSION as REPORT_PROMPT_VERSION
from app.schemas.interview import (
    InterviewConfig,
    InterviewListItem,
    InterviewReplay,
    QuestionItem,
    ReEvaluateResponse,
    StartInterviewResponse,
)
from app.schemas.interview_event import SSEEvent
from app.schemas.interview_message import InterviewMessageOut
from app.schemas.question_bank import QuestionBankSearchItem
from app.services.interview.ai_service import InterviewAIService
from app.services.interview.sse_emitter import SSEEmitter
from app.services.interview.state_machine import NextAction, decide_next
from app.services.interview.style_resolver import resolve_style
from app.services.question_bank import retrieval
from app.services.question_bank.template_service import TemplateService
from app.services.report.service import ReportService

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


@dataclass(frozen=True)
class TurnSnapshot:
    """一条问答回合（答案 + 该轮评分）。"""

    question_index: int
    round: int
    question: str
    answer: str
    score: float | None
    dimensions: dict[str, float]  # completeness/accuracy/depth/clarity
    feedback: str | None


@dataclass(frozen=True)
class InterviewContext:
    """报告生成所需的面试上下文（跨模块只读契约，§3.1）。"""

    interview_id: int
    user_id: int
    position: str
    difficulty: str
    style: str
    resume_summary: str
    questions: list[QuestionItem]
    turns: list[TurnSnapshot]
    answer_quality_avg: float | None


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
        redis: Redis | None = None,
    ) -> StartInterviewResponse:
        resume = await db.get(Resume, resume_id)
        if resume is not None and resume.deleted_at is None:
            if resume.user_id != user_id:
                raise InterviewForbidden()  # 归属校验（§11.3）
            summary = _resume_summary(resume)
        else:
            summary = ""  # 简历缺失/软删：兜底通用题（QG-02）

        # M4 R5：有 company → 检索真题 → 改写融合出题；零命中/检索失败静默回退普通出题
        real_questions: list[QuestionBankSearchItem] | None = None
        if config.company:
            try:
                found = await retrieval.search(
                    db,
                    company=config.company,
                    position=config.position,
                    difficulty=config.difficulty,
                    redis=redis,
                )
                real_questions = found or None
            except Exception as exc:  # 检索/embedding 失败不影响出题主流程（§9.6 零命中回退）
                logger.warning("真题检索失败，静默回退普通出题 company=%s: %s", config.company, exc)
                real_questions = None

        # M4 R7-a：use_templates → 引用题库模板（usage_count 计数）
        templates: list[str] | None = None
        if config.use_templates:
            try:
                templates = await TemplateService.list_for_generation(
                    db, position=config.position, difficulty=config.difficulty
                )
                templates = templates or None
            except Exception as exc:  # 模板引用失败不影响出题主流程
                logger.warning("题库模板引用失败，忽略 position=%s: %s", config.position, exc)
                templates = None

        questions = await ai_service.generate_questions(
            position=config.position,
            difficulty=config.difficulty,
            resume_summary=summary,
            question_count=config.question_count,
            capabilities=config.capabilities,
            real_questions=real_questions,
            templates=templates,
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

    @staticmethod
    async def get_owned_or_none(
        db: AsyncSession,
        *,
        user_id: int,
        interview_id: int,
    ) -> Interview | None:
        """供报告模块校验面试归属（§3.1 只读入口）。不存在/软删/非本人统一返回 None。"""
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None or interview.user_id != user_id:
            return None
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
            # M3：面试结束自动生成报告（红线 4：异步，不在请求内同步调 LLM）。
            # 建行职责在 report 模块的 Service（§3.1 禁止面试模块直操 reports 表）。
            report = await ReportService.create_pending(
                db,
                interview_id=interview_id,
                user_id=interview.user_id,
                prompt_version=REPORT_PROMPT_VERSION,
            )
            try:
                ReportService.enqueue(report.id)
            except Exception:  # 投递失败不破坏面试收尾，报告可由 POST /reports 补触发
                logger.exception("报告任务投递失败 interview_id=%s report_id=%s", interview_id, report.id)

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

    # ------------------------------------------------------------------
    # 历史回放（M4-PR7-b）：列表 / 详情聚合 / 重评（零迁移，复用 messages 表）
    # ------------------------------------------------------------------
    @staticmethod
    async def list(
        db: AsyncSession, *, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[Interview]]:
        page, page_size = parse_pagination(page, page_size)
        cond = (Interview.user_id == user_id, Interview.deleted_at.is_(None))
        total = (await db.execute(select(func.count()).select_from(Interview).where(*cond))).scalar_one()
        stmt = (
            select(Interview)
            .where(*cond)
            .order_by(Interview.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await db.execute(stmt)).scalars().all())
        return int(total), items

    @staticmethod
    def build_list_item(interview: Interview) -> InterviewListItem:
        return InterviewListItem(
            interview_id=interview.id,
            position=interview.position,
            difficulty=interview.difficulty,
            style=interview.style,
            status=interview.status,
            question_count=interview.question_count,
            created_at=interview.created_at.isoformat() if getattr(interview, "created_at", None) else None,
            completed_at=interview.completed_at.isoformat() if interview.completed_at else None,
        )

    @staticmethod
    async def get_replay(
        db: AsyncSession, *, user_id: int, interview_id: int
    ) -> InterviewReplay:
        """回放聚合：题目快照 + 逐条消息 + 报告摘要（只读，§11.3 归属校验）。"""
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None:
            raise InterviewNotFound()
        if interview.user_id != user_id:
            raise InterviewForbidden()
        questions: list[QuestionItem] = []
        for i in range(len(interview.questions_json or [])):
            q = _get_question(interview, i)
            if q is not None:
                questions.append(q)
        messages = await InterviewService.get_messages(db, user_id=user_id, interview_id=interview_id)
        report_summary = None
        report = await ReportService.get_by_interview(db, user_id=user_id, interview_id=interview_id)
        if report is not None:
            payload = report.payload_json if isinstance(report.payload_json, dict) else {}
            report_summary = payload.get("summary")
        return InterviewReplay(
            interview_id=interview.id,
            position=interview.position,
            difficulty=interview.difficulty,
            style=interview.style,
            status=interview.status,
            question_count=interview.question_count,
            questions=questions,
            messages=[m.model_dump() for m in messages],
            report_summary=report_summary,
            created_at=interview.created_at.isoformat() if getattr(interview, "created_at", None) else None,
            completed_at=interview.completed_at.isoformat() if interview.completed_at else None,
        )

    @staticmethod
    async def re_evaluate(
        db: AsyncSession, *, user_id: int, interview_id: int, question_index: int
    ) -> ReEvaluateResponse:
        """重评（独立计费）：对某题作答重新评分，新 score 追加 message，不改原分不改报告。"""
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None:
            raise InterviewNotFound()
        if interview.user_id != user_id:
            raise InterviewForbidden()
        question = _get_question(interview, question_index)
        if question is None:
            raise InterviewInvalidState("当前题目不存在")
        answer, round_ = await _latest_answer(db, interview_id, question_index)
        if answer is None:
            raise InterviewInvalidState("该题暂无作答记录")

        score_data = await ai_service.evaluate_score(question=question, answer=answer)
        db.add(
            InterviewMessage(
                interview_id=interview_id,
                question_index=question_index,
                round=round_,
                role=ROLE_INTERVIEWER,
                content=score_data.feedback,
                event_type="score",
                payload_json={"score": score_data.score, "dimensions": score_data.dimensions, "re_evaluated": True},
            )
        )
        await db.commit()
        return ReEvaluateResponse(
            question_index=question_index,
            score=score_data.score,
            dimensions=score_data.dimensions,
            feedback=score_data.feedback,
        )

    # ------------------------------------------------------------------
    # 报告上下文（M3：跨模块只读出口，§3.1 禁止报告模块直操面试表）
    # ------------------------------------------------------------------
    @staticmethod
    async def load_for_report(
        db: AsyncSession,
        *,
        interview_id: int,
        user_id: int,
    ) -> InterviewContext | None:
        """读取面试上下文（面试 + 逐题问答与评分 + 答题质量均值），供报告生成使用。

        归属不符 / 面试不存在或已软删 → 返回 None（由调用方决定失败路径）。
        """
        interview = await db.get(Interview, interview_id)
        if interview is None or interview.deleted_at is not None or interview.user_id != user_id:
            return None

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
        messages = list((await db.execute(stmt)).scalars().all())

        questions: list[QuestionItem] = []
        q_by_index: dict[int, str] = {}
        for i in range(len(interview.questions_json or [])):
            q = _get_question(interview, i)
            if q is not None:
                questions.append(q)
                q_by_index[i] = q.content

        # score 事件按 (question_index, round) 建索引，用于配对 answer
        score_by_key: dict[tuple[int, int], InterviewMessage] = {}
        for m in messages:
            if m.event_type == "score":
                score_by_key[(m.question_index, m.round)] = m

        turns: list[TurnSnapshot] = []
        turn_means: list[float] = []
        for m in messages:
            if m.event_type != "answer":
                continue
            score: float | None = None
            dims: dict[str, float] = {}
            feedback: str | None = None
            sm = score_by_key.get((m.question_index, m.round))
            if sm is not None and isinstance(sm.payload_json, dict):
                raw_score = sm.payload_json.get("score")
                if isinstance(raw_score, (int, float)):
                    score = float(raw_score)
                raw_dims = sm.payload_json.get("dimensions")
                if isinstance(raw_dims, dict):
                    dims = {str(k): float(v) for k, v in raw_dims.items() if isinstance(v, (int, float))}
                feedback = sm.content
            turns.append(
                TurnSnapshot(
                    question_index=m.question_index,
                    round=m.round,
                    question=q_by_index.get(m.question_index, ""),
                    answer=m.content or "",
                    score=score,
                    dimensions=dims,
                    feedback=feedback,
                )
            )
            if dims:
                turn_means.append(sum(dims.values()) / len(dims))

        answer_quality_avg = round(sum(turn_means) / len(turn_means), 1) if turn_means else None

        resume = await db.get(Resume, interview.resume_id) if interview.resume_id else None
        resume_summary = _resume_summary(resume)

        return InterviewContext(
            interview_id=interview.id,
            user_id=interview.user_id,
            position=interview.position,
            difficulty=interview.difficulty,
            style=interview.style,
            resume_summary=resume_summary,
            questions=questions,
            turns=turns,
            answer_quality_avg=answer_quality_avg,
        )


async def _latest_answer(
    db: AsyncSession,
    interview_id: int,
    question_index: int,
) -> tuple[str | None, int]:
    """取某题最新一轮候选人回答（重评用）；无记录返回 (None, 0)。"""
    stmt = (
        select(InterviewMessage)
        .where(
            InterviewMessage.interview_id == interview_id,
            InterviewMessage.question_index == question_index,
            InterviewMessage.role == ROLE_CANDIDATE,
            InterviewMessage.deleted_at.is_(None),
        )
        .order_by(InterviewMessage.round.desc(), InterviewMessage.id.desc())
        .limit(1)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return None, 0
    return rows[0].content, rows[0].round


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
