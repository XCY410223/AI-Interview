"""题库模板服务（M4 PR-R7-a）：全局模板 CRUD + 出题引用（usage_count 计数）。

分层约束（规范 §4）：session 由 FastAPI Depends 注入，禁止自行 new session。
模板为全局共享沉淀（MVP 无角色系统，任何登录用户可管理，低频管理功能）。
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import QuestionBankNotFound
from app.common.pagination import parse_pagination
from app.models.question_template import QuestionTemplate

logger = logging.getLogger(__name__)

MAX_REFERENCE_TEMPLATES = 5


class TemplateService:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        position: str,
        difficulty: str,
        category: str,
        content: str,
        reference_points: list[str],
        tags: list[str],
    ) -> QuestionTemplate:
        template = QuestionTemplate(
            position=position,
            difficulty=difficulty,
            category=category,
            content=content,
            reference_points=reference_points or None,
            tags=tags or None,
            usage_count=0,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def get(db: AsyncSession, *, template_id: int) -> QuestionTemplate:
        template = await db.get(QuestionTemplate, template_id)
        if template is None or template.deleted_at is not None:
            raise QuestionBankNotFound()
        return template

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        position: str | None = None,
    ) -> tuple[int, list[QuestionTemplate]]:
        page, page_size = parse_pagination(page, page_size)
        count_stmt = select(func.count()).select_from(QuestionTemplate).where(
            QuestionTemplate.deleted_at.is_(None)
        )
        stmt = select(QuestionTemplate).where(QuestionTemplate.deleted_at.is_(None))
        if position:
            count_stmt = count_stmt.where(QuestionTemplate.position == position)
            stmt = stmt.where(QuestionTemplate.position == position)
        total = (await db.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(QuestionTemplate.id.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list((await db.execute(stmt)).scalars().all())
        return int(total), items

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        template: QuestionTemplate,
        position: str | None = None,
        difficulty: str | None = None,
        category: str | None = None,
        content: str | None = None,
        reference_points: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> QuestionTemplate:
        if position is not None:
            template.position = position
        if difficulty is not None:
            template.difficulty = difficulty
        if category is not None:
            template.category = category
        if content is not None:
            template.content = content
        if reference_points is not None:
            template.reference_points = reference_points or None
        if tags is not None:
            template.tags = tags or None
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def delete(db: AsyncSession, *, template: QuestionTemplate) -> None:
        template.deleted_at = template.deleted_at or _now()
        await db.commit()

    @staticmethod
    async def list_for_generation(
        db: AsyncSession,
        *,
        position: str,
        difficulty: str,
        limit: int = MAX_REFERENCE_TEMPLATES,
    ) -> list[str]:
        """出题引用：按岗位+难度取模板内容，并累计 usage_count（§9.6 沉淀机制）。"""
        stmt = (
            select(QuestionTemplate)
            .where(
                QuestionTemplate.deleted_at.is_(None),
                QuestionTemplate.position == position,
                QuestionTemplate.difficulty == difficulty,
            )
            .order_by(QuestionTemplate.usage_count.desc(), QuestionTemplate.id.asc())
            .limit(limit)
        )
        templates = list((await db.execute(stmt)).scalars().all())
        for t in templates:
            t.usage_count = (t.usage_count or 0) + 1
        if templates:
            await db.commit()
        return [t.content for t in templates]


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


__all__ = ["TemplateService", "MAX_REFERENCE_TEMPLATES"]
