"""Interview ORM 模型（表 interviews，M2 计划 §一/§二 PR1）。

字段说明：
- style：friendly/stress/deep（M2-PR4 风格切换，接口入参不变）；
- questions_json：题目快照（JSONB，不参与关系查询，规范 §7.2 允许，仅回显）；
- config_json：场次配置快照（题数/难度/风格）；
- current_question_index / current_round：追问状态机双键（M2-PR3，每题 ≤3 轮追问）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin

# 面试状态机（M2 计划 §二 PR1）
INTERVIEW_STATUS_CREATED = "created"
INTERVIEW_STATUS_IN_PROGRESS = "in_progress"
INTERVIEW_STATUS_COMPLETED = "completed"
INTERVIEW_STATUS_ABANDONED = "abandoned"

# 面试官风格（红线 9 / M2-PR4）
STYLE_FRIENDLY = "friendly"
STYLE_STRESS = "stress"
STYLE_DEEP = "deep"


class Interview(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "interviews"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8, server_default="8"
    )
    style: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STYLE_FRIENDLY, server_default=STYLE_FRIENDLY
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=INTERVIEW_STATUS_CREATED,
        server_default=INTERVIEW_STATUS_CREATED, index=True,
    )
    current_question_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    questions_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # list[QuestionItem]
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
