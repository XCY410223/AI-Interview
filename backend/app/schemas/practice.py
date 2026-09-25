"""弱项专项练习 schema（M4 PR-R7-c）。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.interview import QuestionItem


class PracticeCreateRequest(BaseModel):
    report_id: int
    count: int = Field(ge=1, le=10, default=5)  # 练习题目数上限 10


class PracticeResponse(BaseModel):
    practice_id: int
    report_id: int
    count: int
    questions: list[QuestionItem] = Field(default_factory=list)


__all__ = ["PracticeCreateRequest", "PracticeResponse"]
