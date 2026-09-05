"""ORM 基类（规范 §7）。

约定：
- 表名 snake_case 复数；主键 BIGSERIAL。
- 所有业务表含 created_at / updated_at 审计字段。
- 所有业务表含 deleted_at 软删除字段，查询默认过滤 `deleted_at IS NULL`。
- JSONB 一律 nullable=True，读取方做空值兜底。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PKMixin:
    """主键：BIGSERIAL。"""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    """审计字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """软删除。"""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
