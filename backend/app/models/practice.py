"""弱项专项练习 ORM 模型（表 practice_packs，M4 计划 §四 PR-R7-c）。

由报告 weaknesses 生成针对性题目包（复用出题通道），questions_json 为 JSONB 快照（§7.2）。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin


class PracticePack(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "practice_packs"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    questions_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list[QuestionItem]
