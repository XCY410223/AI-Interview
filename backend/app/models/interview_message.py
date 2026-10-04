"""InterviewMessage ORM 模型（表 interview_messages，M2 计划 §二 PR3）。

逐条记录面试会话消息（候选人回答 + 面试官点评/评分事件），
用于断线重连后的历史回放（GET /messages 恢复现场，规范 §8.2）。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin

# 消息角色
ROLE_CANDIDATE = "candidate"
ROLE_INTERVIEWER = "interviewer"


class InterviewMessage(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "interview_messages"
    __table_args__ = (
        Index("ix_interview_messages_interview_qidx_round", "interview_id", "question_index", "round"),
    )

    interview_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ROLE_CANDIDATE, server_default=ROLE_CANDIDATE
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="chunk", server_default="chunk"
    )
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
