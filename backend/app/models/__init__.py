"""ORM 模型汇总：供 Alembic autogenerate 与跨模块 import 使用。"""
from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin
from app.models.interview import Interview
from app.models.interview_message import InterviewMessage
from app.models.practice import PracticePack
from app.models.question import QuestionBankItem
from app.models.question_template import QuestionTemplate
from app.models.report import Report
from app.models.resume import Resume
from app.models.token import RefreshToken
from app.models.user import User

__all__ = [
    "Base",
    "PKMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "Interview",
    "InterviewMessage",
    "PracticePack",
    "QuestionBankItem",
    "QuestionTemplate",
    "Report",
    "Resume",
    "RefreshToken",
    "User",
]
