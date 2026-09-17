"""ORM 模型汇总：供 Alembic autogenerate 与跨模块 import 使用。"""
from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.interview import Interview
from app.models.resume import Resume
from app.models.token import RefreshToken
from app.models.user import User

__all__ = [
    "Base",
    "PKMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "Interview",
    "Resume",
    "RefreshToken",
    "User",
]
