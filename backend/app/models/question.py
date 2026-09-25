"""题库真题 ORM 模型（表 question_bank_items，M4 计划 §四 PR-R3）。

两种行语义（共用一张表，规范 §9.6 只建一表）：
- **入库作业行**：content 为原始面经文本（可能 >500 字），embedding 为空，status 走状态机
  （pending → processing → completed/failed），由 `rag.ingest(item_id)` 处理；
- **切片 chunk 行**：content 为切片后 chunk（300~500 字），带 embedding，status=completed，
  检索只查 `embedding IS NOT NULL` 的 chunk 行。

content_hash = sha256(company + position + content)，UNIQUE 幂等键（§9.6 可重跑不重复）。
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin

# 入库状态机（规范 §10.2 / M4 计划 §四 PR-R4）
QUESTION_BANK_STATUS_PENDING = "pending"
QUESTION_BANK_STATUS_PROCESSING = "processing"
QUESTION_BANK_STATUS_COMPLETED = "completed"
QUESTION_BANK_STATUS_FAILED = "failed"

# bge-m3 维度（与 settings.EMBEDDING_DIM 保持一致；迁移为静态值）
EMBEDDING_DIM = 1024


class QuestionBankItem(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "question_bank_items"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_question_bank_items_content_hash"),
        Index("ix_question_bank_items_company_position_difficulty", "company", "position", "difficulty"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(10), nullable=False, default="medium", server_default="medium"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 溯源四件套之一
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 幂等键
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)  # 仅 chunk 行
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default=QUESTION_BANK_STATUS_PENDING,
        server_default=QUESTION_BANK_STATUS_PENDING, index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
