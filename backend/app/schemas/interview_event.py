"""SSE 五类事件 Pydantic 模型（规范 §8.2 / 红线 7，M2 计划 §二 PR2）。

评分 JSON 以独立 `score` 事件下发；前端只消费事件，不解析 chunk 文本——
彻底切断「正则从流式文本抠 JSON」的污染路径。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SSEEvent(BaseModel):
    type: Literal["meta", "chunk", "score", "next", "error"]


class MetaEvent(SSEEvent):
    type: Literal["meta"] = "meta"
    interview_id: int
    question_index: int
    round: int


class ChunkEvent(SSEEvent):
    type: Literal["chunk"] = "chunk"
    content: str  # 增量文本片段


class ScoreEvent(SSEEvent):
    type: Literal["score"] = "score"
    score: float = Field(ge=0.0, le=10.0)  # 强制 clamp（规范 §9.3）
    dimensions: dict[str, float] = Field(default_factory=dict)
    feedback: str = ""
    follow_up_suggestion: bool = False  # 触发追问的内部信号


class NextEvent(SSEEvent):
    type: Literal["next"] = "next"
    next_question: str | None = None
    next_question_index: int | None = None
    round: int | None = None  # 下一轮 round（追问时 round+1，下一题时归零）


class ErrorEvent(SSEEvent):
    type: Literal["error"] = "error"
    code: Literal["AI_TIMEOUT", "AI_OVERLOAD", "INTERVIEW_DONE", "INVALID_STATE"]
    message: str
