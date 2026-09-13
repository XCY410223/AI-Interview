"""Resume ORM 模型（表 resumes，含解析状态机，规范 §7.2 / M1 计划 §4.2）。

状态机：pending → processing → completed / failed（瞬时错误回 pending 并 retry_count+1）。
parsed_content 为 JSONB（不参与关系查询的结构化快照，规范 §7.2 允许），读取方必须空值兜底。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin

# 状态机取值（§4.2）
RESUME_STATUS_PENDING = "pending"
RESUME_STATUS_PROCESSING = "processing"
RESUME_STATUS_COMPLETED = "completed"
RESUME_STATUS_FAILED = "failed"


class Resume(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "resumes"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)  # MinIO key，非 URL
    original_ext: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf/docx（小写）
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RESUME_STATUS_PENDING, server_default=RESUME_STATUS_PENDING, index=True
    )
    parsed_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
