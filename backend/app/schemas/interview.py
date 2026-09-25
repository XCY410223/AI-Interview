"""面试模块 schema：场次配置、出题、提交回答（M2 计划 §二 PR1/PR2）。

契约先行冻结：风格/难度/题数在 start 入参一次性确定，之后仅凭 interview_id 推进。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.question_bank import JDCapability


class InterviewConfig(BaseModel):
    position: str = Field(min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_count: int = Field(ge=3, le=15, default=8)  # 规范 §9.5 上限 15
    style: Literal["friendly", "stress", "deep"] = "friendly"  # M2-PR4 启用
    company: str | None = Field(default=None, max_length=100)  # M4 R5：真题 RAG 检索公司
    jd_text: str | None = Field(default=None, max_length=20000)  # M4 R2：JD 原文（入 config_json）
    capabilities: list[JDCapability] | None = None  # M4 R2：JD 能力项（可选注入出题）
    use_templates: bool = False  # M4 R7-a：是否引用题库模板出题


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
    source: str | None = None  # M4 R5：真题溯源回显（{company}·{source_url}）


class StartInterviewResponse(BaseModel):
    interview_id: int
    total_questions: int
    first_question: QuestionItem
    estimated_minutes: int


class SubmitAnswerRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)  # §9.4 回答上限 4000 字
    round: int = Field(ge=0, default=0)


# ---- 历史回放（M4 PR-R7-b：列表 / 详情聚合 / 重评，零迁移）----
class InterviewListItem(BaseModel):
    interview_id: int
    position: str
    difficulty: str
    style: str
    status: str
    question_count: int
    created_at: str | None = None
    completed_at: str | None = None


class ReEvaluateResponse(BaseModel):
    question_index: int
    score: float
    dimensions: dict[str, float] = Field(default_factory=dict)
    feedback: str = ""


class InterviewReplay(BaseModel):
    interview_id: int
    position: str
    difficulty: str
    style: str
    status: str
    question_count: int
    questions: list[QuestionItem] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    report_summary: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
