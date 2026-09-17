"""SSE 事件组装器（M2-PR2）：强类型 Pydantic 事件 → SSE 文本协议。

评分 JSON 强制 clamp（规范 §9.3）：score 越界收敛到 [0,10]，一位小数；
维度字典键非字符串/值非数字时兜底过滤。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.schemas.interview_event import (
    ChunkEvent,
    ErrorEvent,
    MetaEvent,
    NextEvent,
    ScoreEvent,
    SSEEvent,
)

_MAX_SCORE = 10.0
_MIN_SCORE = 0.0


def clamp_score(value: float) -> float:
    """评分 clamp 到 [0,10] 并四舍五入一位小数（规范 §9.3）。"""
    clamped = max(_MIN_SCORE, min(_MAX_SCORE, float(value)))
    return round(clamped, 1)


def sanitize_dimensions(raw: dict | None) -> dict[str, float]:
    """维度字典清洗：仅保留数值型值，非数值/非法键丢弃。"""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in raw.items():
        try:
            result[str(key)] = clamp_score(float(value))
        except (TypeError, ValueError):
            continue
    return result


class SSEEmitter:
    """五类事件构造器 + 序列化（meta/chunk/score/next/error）。"""

    @staticmethod
    def meta(interview_id: int, question_index: int, round_: int) -> MetaEvent:
        return MetaEvent(interview_id=interview_id, question_index=question_index, round=round_)

    @staticmethod
    def chunk(content: str) -> ChunkEvent:
        return ChunkEvent(content=content)

    @staticmethod
    def score(raw: dict) -> ScoreEvent:
        """评分事件：score 强制 clamp，维度字典清洗（SSE-05/06/11）。"""
        try:
            score = clamp_score(float(raw.get("score", 0.0)))
        except (TypeError, ValueError):
            score = 0.0
        return ScoreEvent(
            score=score,
            dimensions=sanitize_dimensions(raw.get("dimensions")),
            feedback=str(raw.get("feedback", "")),
            follow_up_suggestion=bool(raw.get("follow_up_suggestion", False)),
        )

    @staticmethod
    def next(
        next_question: str | None, next_question_index: int | None, round_: int | None
    ) -> NextEvent:
        return NextEvent(next_question=next_question, next_question_index=next_question_index, round=round_)

    @staticmethod
    def error(code: str, message: str) -> ErrorEvent:
        # code 为协议枚举；调用方保证传合法值（AI_TIMEOUT / AI_OVERLOAD / INTERVIEW_DONE / INVALID_STATE）
        return ErrorEvent(code=code, message=message)  # type: ignore[arg-type]

    @staticmethod
    async def serialize(events: AsyncIterator[SSEEvent]) -> AsyncIterator[str]:
        """强类型事件 → SSE 文本（data: {json}\\n\\n）。"""
        async for event in events:
            yield f"data: {event.model_dump_json()}\n\n"


__all__ = ["SSEEmitter", "clamp_score", "sanitize_dimensions"]
