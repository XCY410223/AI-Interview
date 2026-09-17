"""面试模块 schema：场次配置、出题（M2 计划 §二 PR1）。

契约先行冻结：风格/难度/题数在 start 入参一次性确定，之后仅凭 interview_id 推进。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InterviewConfig(BaseModel):
    position: str = Field(min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_count: int = Field(ge=3, le=15, default=8)  # 规范 §9.5 上限 15
    style: Literal["friendly", "stress", "deep"] = "friendly"  # M2-PR4 启用


class StartInterviewRequest(BaseModel):
    resume_id: int
    config: InterviewConfig


class QuestionItem(BaseModel):
    question_index: int = Field(ge=0)
    round: int = Field(ge=0, default=0)  # M2-PR3 启用
    category: str
    content: str
    reference_points: list[str] = Field(default_factory=list)
    difficulty: str


class StartInterviewResponse(BaseModel):
    interview_id: int
    total_questions: int
    first_question: QuestionItem
    estimated_minutes: int
