"""RefreshToken ORM 模型（表 refresh_tokens，规范 §11.2 / M1 计划 §3.2）。

只存 jti+secret 的 sha256 哈希，不存 token 原文；revoked/replaced_by 支撑轮换与整链撤销。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class RefreshToken(Base, PKMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    # 轮换链：旧 token 的 replaced_by 指向新 token（§3.4 整链撤销）
    replaced_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("refresh_tokens.id"), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
