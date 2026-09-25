"""题库模块 schema（JD 解析 / 真题 RAG / 模板库，M4 计划 §四 PR-R1/R4/R7-a）。

契约先行冻结（规范 §6.2）：
- JD 解析：jd_text 50~20000 字，能力项 5~15 项，每项关键词 2~5 个；
- 真题入库：文本粘贴 + 元数据（不做文件上传，M4 决策 D6）；
- 模板库：position/difficulty 维度 + tags JSONB。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel

# 能力项类别（JD 解析契约，前后端对齐）
CAPABILITY_CATEGORIES = ("hard_skill", "soft_skill", "domain", "experience")
CAPABILITY_IMPORTANCE = ("must", "nice_to_have")

# 真题入库难度（与面试 difficulty 对齐）
QUESTION_DIFFICULTY = ("easy", "medium", "hard")


class JDParseRequest(BaseModel):
    """JD 粘贴原文 → 解析能力项清单（M4 PR-R1）。"""

    jd_text: str = Field(min_length=50, max_length=20000)


class JDCapability(BaseModel):
    """单条能力项：名称 / 类别 / 可匹配关键词 / 重要级。"""

    name: str = Field(min_length=1, max_length=100)
    category: Literal["hard_skill", "soft_skill", "domain", "experience"]
    keywords: list[str] = Field(min_length=2, max_length=5)
    importance: Literal["must", "nice_to_have"]


class JDParseResponse(BaseModel):
    """JD 解析结果：岗位名 + 能力项清单（5~15 项）。"""

    position_guess: str
    capabilities: list[JDCapability] = Field(min_length=5, max_length=15)
    parsed_at: datetime


class IngestRequest(BaseModel):
    """面经入库（文本粘贴，M4 决策 D6：不做文件上传）。"""

    company: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    content: str = Field(min_length=1, max_length=20000)
    source_url: str | None = Field(default=None, max_length=500)


class IngestResponse(BaseModel):
    item_id: int
    status: str
    task_id: str | None = None


class QuestionBankSearchRequest(BaseModel):
    company: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    top_k: int = Field(default=8, ge=1, le=32)


class QuestionBankSearchItem(BaseModel):
    id: int
    company: str
    position: str
    difficulty: str
    content: str
    source_url: str | None = None


class QuestionBankSearchResponse(BaseModel):
    items: list[QuestionBankSearchItem]


class QuestionTemplateCreate(BaseModel):
    position: str = Field(min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    category: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=2000)
    reference_points: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class QuestionTemplateUpdate(BaseModel):
    position: str | None = Field(default=None, min_length=1, max_length=100)
    difficulty: Literal["easy", "medium", "hard"] | None = None
    category: str | None = Field(default=None, min_length=1, max_length=50)
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    reference_points: list[str] | None = None
    tags: list[str] | None = None


class QuestionTemplateOut(ORMModel):
    id: int
    position: str
    difficulty: str
    category: str
    content: str
    reference_points: list = Field(default_factory=list)
    tags: list = Field(default_factory=list)
    usage_count: int = 0
    created_at: datetime | None = None


__all__ = [
    "CAPABILITY_CATEGORIES",
    "CAPABILITY_IMPORTANCE",
    "QUESTION_DIFFICULTY",
    "JDParseRequest",
    "JDCapability",
    "JDParseResponse",
    "IngestRequest",
    "IngestResponse",
    "QuestionBankSearchRequest",
    "QuestionBankSearchItem",
    "QuestionBankSearchResponse",
    "QuestionTemplateCreate",
    "QuestionTemplateOut",
]
