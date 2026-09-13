"""简历服务：创建 pending 记录 + 下发解析任务 + 状态查询（M1 计划 §4.4）。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ResumeForbidden, ResumeNotFound
from app.common.pagination import parse_pagination
from app.models.resume import RESUME_STATUS_PENDING, Resume

logger = logging.getLogger(__name__)


class ResumeService:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: int,
        object_key: str,
        original_ext: str,
        size_bytes: int,
        mime_type: str,
    ) -> Resume:
        resume = Resume(
            user_id=user_id,
            object_key=object_key,
            original_ext=original_ext,
            size_bytes=size_bytes,
            mime_type=mime_type,
            status=RESUME_STATUS_PENDING,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)
        logger.info("resume uploaded user_id=%s resume_id=%s", user_id, resume.id)
        return resume

    @staticmethod
    def enqueue(resume_id: int) -> str:
        """下发解析任务，返回 Celery task_id（延迟导入避免循环依赖）。"""
        from app.tasks.resume_parser import parse_resume_task

        result = parse_resume_task.delay(resume_id=resume_id)
        return str(getattr(result, "id", "") or "")

    @staticmethod
    async def get(db: AsyncSession, *, user_id: int, resume_id: int) -> Resume:
        resume = await db.get(Resume, resume_id)
        if resume is None or resume.deleted_at is not None:
            raise ResumeNotFound()
        if resume.user_id != user_id:
            raise ResumeForbidden()  # 归属校验（§11.3）
        return resume

    @staticmethod
    async def list(
        db: AsyncSession, *, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[Resume]]:
        page, page_size = parse_pagination(page, page_size)
        cond = (Resume.user_id == user_id, Resume.deleted_at.is_(None))
        total = (await db.execute(select(func.count()).select_from(Resume).where(*cond))).scalar_one()
        stmt = select(Resume).where(*cond).order_by(Resume.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list((await db.execute(stmt)).scalars().all())
        return int(total), items
