"""弱项专项练习服务（M4 PR-R7-c）：取报告弱项 → 生成针对性题目包（复用出题通道）。

分层约束（规范 §4）：session 由 FastAPI Depends 注入；LLM 调用走 ai_service（红线 6）。
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import PracticeNotFound, ReportNotReady
from app.models.practice import PracticePack
from app.models.report import REPORT_STATUS_COMPLETED
from app.schemas.interview import QuestionItem
from app.services.interview.service import ai_service
from app.services.report.service import ReportService

logger = logging.getLogger(__name__)


def _weaknesses(payload: dict) -> list[str]:
    raw = payload.get("weaknesses")
    if isinstance(raw, list):
        items = [str(w) for w in raw if w]
        if items:
            return items
    suggestions = payload.get("suggestions")
    if isinstance(suggestions, list):
        return [str(s) for s in suggestions if s]
    return []


class PracticeService:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: int,
        report_id: int,
        count: int,
    ) -> PracticePack:
        report = await ReportService.get(db, user_id=user_id, report_id=report_id)
        if report.status != REPORT_STATUS_COMPLETED:
            raise ReportNotReady("报告尚未生成完成，暂无法生成专项练习")

        payload = report.payload_json if isinstance(report.payload_json, dict) else {}
        weaknesses = _weaknesses(payload)
        questions: list[QuestionItem] = await ai_service.generate_practice(
            weaknesses=weaknesses, count=count
        )
        pack = PracticePack(
            user_id=user_id,
            report_id=report_id,
            status="completed",
            count=len(questions),
            questions_json=[q.model_dump() for q in questions],
        )
        db.add(pack)
        await db.commit()
        await db.refresh(pack)
        logger.info("practice pack created pack_id=%s report_id=%s count=%s", pack.id, report_id, len(questions))
        return pack

    @staticmethod
    async def get(db: AsyncSession, *, user_id: int, practice_id: int) -> PracticePack:
        pack = await db.get(PracticePack, practice_id)
        if pack is None or pack.deleted_at is not None or pack.user_id != user_id:
            raise PracticeNotFound()
        return pack


__all__ = ["PracticeService"]
