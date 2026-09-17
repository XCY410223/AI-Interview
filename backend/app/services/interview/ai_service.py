"""面试 AI 编排（M2-PR1）：出题。

红线 6：所有模型调用走统一 LLM 客户端；
红线 5：结构化输出协议 + Pydantic 校验，禁止正则抠 JSON；
红线 9：prompt 全部来自 app/prompts/interview 版本化模块。
"""
from __future__ import annotations

import logging

from app.core.llm.client import LLMClient, LLMError, llm_client
from app.prompts.interview.question_generation import QUESTION_GENERATION_PROMPT
from app.schemas.interview import QuestionItem

logger = logging.getLogger(__name__)

# 出题兜底分布（近似 30/40/20/10）
_FALLBACK_CATEGORIES = ("知识", "项目", "项目", "行为", "知识", "项目", "行为", "算法")

# 结构校验/解析重试次数：LLM 客户端已处理网络重试，这里只管「结构非法 → 重试 1 次 → 兜底」
_PARSE_RETRIES = 2


class InterviewAIService:
    """LLM 调用编排入口：出题。`client` 用于测试注入 fake，不传则复用全局统一客户端。"""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client if client is not None else llm_client

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


__all__ = ["InterviewAIService"]
