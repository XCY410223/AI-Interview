"""历史回放消息 schema（含 question_index + round，M2 计划 §二 PR3）。"""
from __future__ import annotations

from datetime import datetime

from app.schemas.base import ORMModel


class InterviewMessageOut(ORMModel):
    id: int
    question_index: int
    round: int
    role: str
    content: str | None = None
    event_type: str
    payload_json: dict | None = None
    created_at: datetime | None = None
