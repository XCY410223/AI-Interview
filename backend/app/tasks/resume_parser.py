"""简历解析 Celery 任务（幂等 + 状态回写，规范 §10.2 / M1 计划 §5.2）。

状态机：pending → processing → completed / failed（瞬时错误回 pending 并 retry_count+1，§4.2）。
入参只接 resume_id（§10.2）；worker 内独立 session，事务边界严格在任务内。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

from app.common.exceptions import AIClientError
from app.core.database import async_session_factory
from app.core.storage import StorageClient, get_storage
from app.models.resume import (
    RESUME_STATUS_COMPLETED,
    RESUME_STATUS_FAILED,
    RESUME_STATUS_PENDING,
    RESUME_STATUS_PROCESSING,
    Resume,
)
from app.services.resume.parser_service import extract_text, parse_text

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


@shared_task(
    bind=True,
    name="resume.parse",
    max_retries=MAX_RETRIES,
    default_retry_delay=15,
    retry_backoff=True,
    retry_jitter=True,
    time_limit=180,
    soft_time_limit=150,
)
def parse_resume_task(self, resume_id: int) -> dict:
    """Celery 入口：入参只接 resume_id。"""
    return asyncio.run(_run(resume_id, task=self))


async def _run(
    resume_id: int,
    *,
    task=None,
    session_factory=async_session_factory,
    storage: StorageClient | None = None,
) -> dict:
    """任务主体（独立函数便于注入 fake 单测）。"""
    storage = storage or get_storage()

    async with session_factory() as db:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            return {"status": "not_found", "resume_id": resume_id}
        if resume.status == RESUME_STATUS_COMPLETED:
            return {"status": "skipped", "resume_id": resume_id}
        object_key = resume.object_key
        original_ext = resume.original_ext
        resume.status = RESUME_STATUS_PROCESSING
        await db.commit()

    try:
        content = await storage.get_object(object_key)
        text = extract_text(content, original_ext)
        parsed = await parse_text(text)
    except AIClientError as exc:
        exhausted = await _handle_retry(session_factory, resume_id, exc)
        if exhausted:
            return {"status": "failed", "resume_id": resume_id, "error": str(exc)}
        if task is not None:
            raise task.retry(exc=exc)
        raise exc
    except Exception as exc:
        await _mark_failed(session_factory, resume_id, str(exc))
        raise

    async with session_factory() as db:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            return {"status": "not_found", "resume_id": resume_id}
        resume.parsed_content = parsed.model_dump()
        resume.status = RESUME_STATUS_COMPLETED
        resume.processed_at = datetime.now(timezone.utc)
        resume.error_message = None
        await db.commit()
    logger.info("resume parsed resume_id=%s", resume_id)
    return {"status": "completed", "resume_id": resume_id}


async def _handle_retry(session_factory, resume_id: int, exc: AIClientError) -> bool:
    """瞬时错误：retry_count+1；耗尽 → failed（返回 True），否则回 pending（返回 False）。"""
    async with session_factory() as db:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            return True
        resume.retry_count += 1
        if resume.retry_count > MAX_RETRIES:
            resume.status = RESUME_STATUS_FAILED
            resume.error_message = str(exc)
            await db.commit()
            return True
        resume.status = RESUME_STATUS_PENDING
        await db.commit()
        return False


async def _mark_failed(session_factory, resume_id: int, message: str) -> None:
    async with session_factory() as db:
        resume = await db.get(Resume, resume_id)
        if resume is not None:
            resume.status = RESUME_STATUS_FAILED
            resume.error_message = message
            await db.commit()
