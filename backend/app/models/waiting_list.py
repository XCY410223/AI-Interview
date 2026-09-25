"""WaitingList ORM 模型（表 waiting_list，M4 计划 §四 PR-R7-d）。

增长机制：公开接口收集意向邮箱，email 唯一防重；发送确认信（tasks/email.py）。
"""
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin


class WaitingList(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "waiting_list"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
