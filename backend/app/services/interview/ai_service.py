"""面试 AI 编排（M2-PR1/PR2/PR3）：出题 / 评语流 / 评分结构化 / 追问决策。

红线 6：所有模型调用走统一 LLM 客户端；
红线 5：结构化输出协议 + Pydantic 校验，禁止正则抠 JSON；
红线 9：prompt 全部来自 app/prompts/interview 版本化模块；
规范 §9.4：候选人回答只进 role=user 段，系统指令固定 role=system。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.llm.client import LLMClient, LLMError, llm_client
from app.prompts.interview.answer_evaluation import EVALUATION_FEEDBACK_PROMPT, EVALUATION_SCORE_PROMPT
from app.prompts.interview.follow_up_decision import FOLLOW_UP_DECISION_PROMPT
from app.prompts.interview.question_generation import QUESTION_GENERATION_PROMPT
from app.schemas.interview import QuestionItem
from app.services.interview.style_resolver import StylePrompts

logger = logging.getLogger(__name__)

# 兜底（M2 计划 QG-05 / SSE-04 / SSE-12）
FALLBACK_SCORE = 5.0
# 出题兜底分布（近似 30/40/20/10）
_FALLBACK_CATEGORIES = ("知识", "项目", "项目", "行为", "知识", "项目", "行为", "算法")

# 结构校验/解析重试次数：LLM 客户端已处理网络重试，这里只管「结构非法 → 重试 1 次 → 兜底」
_PARSE_RETRIES = 2


@dataclass(frozen=True)
class EvaluationScore:
    score: float
    dimensions: dict[str, float]
    feedback: str


@dataclass(frozen=True)
class FollowUpDecision:
    need_follow_up: bool
    follow_up_hint: str
    reason: str


def _chunk_text(text: str, size: int = 24) -> list[str]:
    """把整段文本切成小块（模拟流式，供无流式能力的客户端兜底）。"""
    if not text:
        return [""]
    return [text[i : i + size] for i in range(0, len(text), size)]


def _join_points(points: list[str]) -> str:
    return "、".join(points) if points else "（无，请基于常识评估）"


def _format_history(history: list[str]) -> str:
    if not history:
        return "（首轮回答，无前几轮）"
    return "\n".join(f"第 {i + 1} 轮：{a}" for i, a in enumerate(history))


class InterviewAIService:
    """LLM 调用编排入口：出题 / 评分（评语流分离）/ 追问决策。`client` 用于测试注入 fake。"""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client if client is not None else llm_client

    # ------------------------------------------------------------------
    # 出题（M2-PR1）
    # ------------------------------------------------------------------
    async def generate_questions(
        self,
        *,
        position: str,
        difficulty: str,
        resume_summary: str,
        question_count: int,
    ) -> list[QuestionItem]:
        summary = resume_summary.strip() or "（无简历信息，出通用题）"
        system = QUESTION_GENERATION_PROMPT.format(
            position=position,
            difficulty=difficulty,
            question_count=question_count,
            resume_summary=summary,
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": summary}]
        for attempt in range(_PARSE_RETRIES):
            try:
                result = await self._client.chat(messages, json_mode=True)
                return self._parse_questions(result.data or {}, question_count)
            except (LLMError, KeyError, TypeError, ValueError) as exc:
                if attempt == 0:
                    logger.warning("出题 JSON 解析失败，重试 1 次: %s", exc)
                    continue
                logger.error("出题两次失败，走兜底题: %s", exc)
                return self._fallback_questions(position, question_count)
        return self._fallback_questions(position, question_count)  # pragma: no cover

    # ------------------------------------------------------------------
    # 评分：评语流（stream → chunk）与评分 JSON（json_object → score）分离
    # ------------------------------------------------------------------
    async def stream_feedback(
        self,
        *,
        question: QuestionItem,
        answer: str,
        style: StylePrompts,
    ) -> AsyncIterator[str]:
        system = EVALUATION_FEEDBACK_PROMPT.format(
            feedback_tone=style.feedback_tone,
            question_content=question.content,
            reference_points=_join_points(question.reference_points),
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": answer}]
        streamer = getattr(self._client, "chat_stream", None)
        if streamer is None:
            # 无流式能力：整段返回后切块（保证 chunk 事件契约不变）
            result = await self._client.chat(messages)
            for piece in _chunk_text(result.content or ""):
                yield piece
            return
        async for delta in streamer(messages):
            yield delta

    async def evaluate_score(
        self,
        *,
        question: QuestionItem,
        answer: str,
    ) -> EvaluationScore:
        system = EVALUATION_SCORE_PROMPT.format(
            question_content=question.content,
            reference_points=_join_points(question.reference_points),
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": answer}]
        for attempt in range(_PARSE_RETRIES):
            try:
                result = await self._client.chat(messages, json_mode=True)
                return self._parse_score(result.data or {})
            except (LLMError, KeyError, TypeError, ValueError) as exc:
                if attempt == 0:
                    logger.warning("评分 JSON 解析失败，重试 1 次: %s", exc)
                    continue
                logger.error("评分两次失败，兜底 %.1f: %s", FALLBACK_SCORE, exc)
        return EvaluationScore(score=FALLBACK_SCORE, dimensions={}, feedback="评分失败，兜底")

    # ------------------------------------------------------------------
    # 追问决策（M2-PR3）
    # ------------------------------------------------------------------
    async def decide_follow_up(
        self,
        *,
        question: QuestionItem,
        answer_history: list[str],
        current_round: int,
        style: StylePrompts,
    ) -> FollowUpDecision:
        system = FOLLOW_UP_DECISION_PROMPT.format(
            followup_tone=style.followup_tone,
            question_content=question.content,
            reference_points=_join_points(question.reference_points),
            current_round=current_round,
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": _format_history(answer_history)}]
        for attempt in range(_PARSE_RETRIES):
            try:
                result = await self._client.chat(messages, json_mode=True)
                return self._parse_followup(result.data or {})
            except (LLMError, KeyError, TypeError, ValueError) as exc:
                if attempt == 0:
                    logger.warning("追问决策 JSON 解析失败，重试 1 次: %s", exc)
                    continue
                logger.error("追问决策两次失败，兜底不追问: %s", exc)
        return FollowUpDecision(need_follow_up=False, follow_up_hint="", reason="判定失败，兜底不追问")

    # ------------------------------------------------------------------
    # 解析器（结构化输出 + Pydantic 校验）
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_questions(data: dict, question_count: int) -> list[QuestionItem]:
        raw = data.get("questions")
        if not isinstance(raw, list) or not raw:
            raise ValueError("questions 非数组或为空")
        items: list[QuestionItem] = []
        for i, q in enumerate(raw):
            if not isinstance(q, dict):
                raise ValueError("question 非对象")
            items.append(
                QuestionItem(
                    question_index=i,
                    round=0,
                    category=str(q.get("category", "项目")),
                    content=str(q.get("content", "")),
                    reference_points=[str(p) for p in (q.get("reference_points") or [])],
                    difficulty=str(q.get("difficulty", "medium")),
                )
            )
        return items[:question_count]

    @staticmethod
    def _parse_score(data: dict) -> EvaluationScore:
        raw_score = data.get("score")
        if raw_score is None:
            raise ValueError("score 缺失")
        score = float(raw_score)
        dimensions = data.get("dimensions")
        if not isinstance(dimensions, dict):
            dimensions = {}
        return EvaluationScore(
            score=score,
            dimensions={str(k): float(v) for k, v in dimensions.items()},
            feedback=str(data.get("feedback", "")),
        )

    @staticmethod
    def _parse_followup(data: dict) -> FollowUpDecision:
        return FollowUpDecision(
            need_follow_up=bool(data.get("need_follow_up", False)),
            follow_up_hint=str(data.get("follow_up_hint", "")),
            reason=str(data.get("reason", "")),
        )

    @staticmethod
    def _fallback_questions(position: str, question_count: int) -> list[QuestionItem]:
        items: list[QuestionItem] = []
        for i in range(question_count):
            category = _FALLBACK_CATEGORIES[i % len(_FALLBACK_CATEGORIES)]
            items.append(
                QuestionItem(
                    question_index=i,
                    round=0,
                    category=category,
                    content=f"请结合你的经历，谈谈与「{position}」岗位相关的核心能力（{category}类）。",
                    reference_points=["回答完整性", "技术深度", "表达清晰"],
                    difficulty="medium",
                )
            )
        return items


__all__ = ["EvaluationScore", "FollowUpDecision", "FALLBACK_SCORE", "InterviewAIService"]
