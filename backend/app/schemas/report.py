"""报告模块 schema（M3 契约层，**先冻结后实现**，规范 §7.2/§9.3）。

冻结要点（PR1 合并后不得擅自改动）：
1. 维度 key 与顺序 —— 前后端 PDF/雷达图共用；
2. grade 五档阈值 —— 服务端计算，LLM 不自报；
3. overall_score 由 6 维均值推出，不接受 LLM 自报总分；
4. 分数范围 0~10 一位小数，服务端 clamp；
5. JSONB 字段一律可空，读取方必须空值兜底。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---- 雷达维度定义（前后端唯一真源，前端 types/index.ts 须逐字对齐）----
DIMENSION_KEYS: tuple[str, ...] = (
    "fundamentals",        # 基础知识
    "technical_depth",     # 技术深度
    "project_experience",  # 项目经验
    "logical_thinking",    # 逻辑思维
    "communication",       # 表达沟通
    "job_fit",             # 岗位匹配
)
DIMENSION_LABELS: dict[str, str] = {
    "fundamentals": "基础知识",
    "technical_depth": "技术深度",
    "project_experience": "项目经验",
    "logical_thinking": "逻辑思维",
    "communication": "表达沟通",
    "job_fit": "岗位匹配",
}
DIMENSION_MAX = 10.0

# 等级档位（服务端唯一口径，禁止 LLM 自报）
GRADE_EXCELLENT = "优秀"    # >= 9.0
GRADE_GOOD = "良好"         # >= 8.0
GRADE_QUALIFIED = "合格"    # >= 7.0
GRADE_IMPROVING = "待提升"  # <  7.0
GradeT = Literal["优秀", "良好", "合格", "待提升"]

GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (9.0, GRADE_EXCELLENT),
    (8.0, GRADE_GOOD),
    (7.0, GRADE_QUALIFIED),
)


def grade_of(score: float) -> str:
    """总分 → 等级（服务端唯一计算口径）。"""
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return GRADE_IMPROVING


def _clamp_score(value: float) -> float:
    """分数 clamp 到 [0, 10] 并保留一位小数（规范 §9.3）。"""
    return round(max(0.0, min(float(value), DIMENSION_MAX)), 1)


class DimensionScore(BaseModel):
    key: str
    name: str = ""
    score: float = 0.0  # clamp 由 ReportPayload 归位时统一处理
    comment: str = ""


class QuestionScore(BaseModel):
    question_index: int = Field(ge=0)
    round: int = Field(ge=0, default=0)
    question: str = ""
    score: float = 0.0
    feedback: str = ""


class ReportPayload(BaseModel):
    """LLM 结构化输出契约（json_object 模式，§9.2/§9.3）。"""

    summary: str = Field(min_length=1, max_length=500)
    dimensions: list[DimensionScore]
    strengths: list[str] = Field(default_factory=list, max_length=6)
    weaknesses: list[str] = Field(default_factory=list, max_length=6)
    suggestions: list[str] = Field(default_factory=list, max_length=6)
    hire_recommendation: str = ""
    question_scores: list[QuestionScore] = Field(default_factory=list)

    @field_validator("dimensions")
    @classmethod
    def _normalize_dimensions(cls, value: list[DimensionScore]) -> list[DimensionScore]:
        """按 DIMENSION_KEYS 归位、补齐缺失维度（中性 5.0）、裁掉多余维度、强制顺序并 clamp。"""
        by_key: dict[str, DimensionScore] = {}
        for d in value:
            by_key[d.key] = DimensionScore(
                key=d.key,
                name=d.name or DIMENSION_LABELS.get(d.key, d.key),
                score=_clamp_score(d.score),
                comment=d.comment,
            )
        ordered: list[DimensionScore] = []
        for key in DIMENSION_KEYS:
            if key in by_key:
                ordered.append(by_key[key])
            else:
                ordered.append(DimensionScore(key=key, name=DIMENSION_LABELS[key], score=5.0, comment=""))
        return ordered

    @field_validator("question_scores")
    @classmethod
    def _clamp_question_scores(cls, value: list[QuestionScore]) -> list[QuestionScore]:
        for q in value:
            q.score = _clamp_score(q.score)
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> "ReportPayload":
        """维度齐全性校验（归位后必须与 DIMENSION_KEYS 逐字对齐）。"""
        keys = [d.key for d in self.dimensions]
        if keys != list(DIMENSION_KEYS):
            raise ValueError(f"报告维度缺失或顺序错误: {keys}")
        return self

    @property
    def overall_score(self) -> float:
        """总分 = 6 维均值，保留一位小数（服务端计算，不接受 LLM 自报）。"""
        if not self.dimensions:
            return 0.0
        return round(sum(d.score for d in self.dimensions) / len(self.dimensions), 1)

    @property
    def grade(self) -> str:
        return grade_of(self.overall_score)


# ---- API 出入参（§8.1 分页、§6.3 统一响应）----
class CreateReportRequest(BaseModel):
    interview_id: int


class CreateReportResponse(BaseModel):
    report_id: int
    status: str


class ReportDetail(BaseModel):
    report_id: int
    interview_id: int
    status: str
    prompt_version: str | None = None
    overall_score: float | None = None
    grade: str | None = None
    summary: str | None = None
    dimensions: list[DimensionScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    hire_recommendation: str | None = None
    question_scores: list[QuestionScore] = Field(default_factory=list)
    answer_quality_avg: float | None = None
    pdf_ready: bool = False
    pdf_error_message: str | None = None
    error_message: str | None = None
    generated_at: str | None = None


class ReportListItem(BaseModel):
    report_id: int
    interview_id: int
    status: str
    overall_score: float | None = None
    grade: str | None = None
    generated_at: str | None = None
