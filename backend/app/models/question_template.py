"""题库模板 ORM 模型（表 question_templates，M4 计划 §四 PR-R7-a）。

全局共享的题库模板沉淀（无 user 归属，MVP 无角色系统）；出题可选引用（config.use_templates）。
reference_points / tags 为 JSONB（不参与关系查询，§7.2 允许，仅回显/注入出题）。
"""
from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin


class QuestionTemplate(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "question_templates"

    position: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium", server_default="medium"
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reference_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list[str]
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list[str]
    usage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
