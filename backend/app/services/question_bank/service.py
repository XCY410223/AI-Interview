"""题库服务（M4 PR-R4/R5）：面经入库建行 + 下发 Celery 任务 + 溯源 URL 校验。

分层约束（规范 §4）：本层负责建行/校验/下发；入库管线（切片→去重→embedding→入库）
在 Celery 任务内（红线 4：embedding 属 AI 调用，禁止在 HTTP 请求内同步执行）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import QuestionBankInvalidSource
from app.models.question import QUESTION_BANK_STATUS_PENDING, QuestionBankItem
from app.services.question_bank.ingest import job_content_hash

logger = logging.getLogger(__name__)


def validate_source_url(source_url: str | None) -> None:
    """溯源 URL 仅接受公开 http(s)（§9.6 禁令：登录/付费/robots 禁止源不在此列，交人工确认）。"""
    if not source_url:
        return
    parsed = urlparse(source_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise QuestionBankInvalidSource()


class QuestionBankService:
    @staticmethod
    async def create_ingest(
        db: AsyncSession,
        *,
        user_id: int,
        company: str,
        position: str,
        difficulty: str,
        content: str,
        source_url: str | None,
    ) -> QuestionBankItem:
        """创建入库作业行（content=原始面经，embedding 空，status=pending）并下发任务。"""
        validate_source_url(source_url)
        item = QuestionBankItem(
            user_id=user_id,
            company=company,
            position=position,
            difficulty=difficulty,
            content=content,
            source_url=source_url or None,
            collected_at=datetime.now(timezone.utc),
            content_hash=job_content_hash(company, position, content),
            status=QUESTION_BANK_STATUS_PENDING,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        logger.info("question_bank ingest created item_id=%s company=%s position=%s", item.id, company, position)
        return item

    @staticmethod
    def enqueue(item_id: int) -> str:
        """下发入库任务，返回 Celery task_id（延迟导入避免循环依赖）。"""
        from app.tasks.rag import ingest_item_task

        result = ingest_item_task.delay(item_id=item_id)
        return str(getattr(result, "id", "") or "")


__all__ = ["QuestionBankService", "validate_source_url"]
