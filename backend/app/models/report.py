"""Report ORM 模型（表 reports，含生成状态机，规范 §7.2 / M3 计划 §三）。

状态机：pending → processing → completed / failed（瞬时错误回 pending 并 retry_count+1）。
dimensions_json / payload_json 为 JSONB 快照（不参与关系查询，§7.2 允许），读取方必须空值兜底。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin

# 状态机取值（M3 计划 §三）
REPORT_STATUS_PENDING = "pending"
REPORT_STATUS_PROCESSING = "processing"
REPORT_STATUS_COMPLETED = "completed"
REPORT_STATUS_FAILED = "failed"


class Report(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"

    interview_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=REPORT_STATUS_PENDING,
        server_default=REPORT_STATUS_PENDING, index=True,
    )
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dimensions_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # 6 维明细快照
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)     # 完整报告产物
    pdf_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # MinIO key（红线 8）
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # PDF 导出永久失败原因（报告本身已完成）
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
