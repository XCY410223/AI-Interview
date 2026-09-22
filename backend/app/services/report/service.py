"""报告服务：创建 pending 行、幂等、查询、序列化（M3 计划 §二/§六/§七）。

分层约束（规范 §4）：本层负责报告聚合/归属校验/产物组装；session 由 FastAPI
Depends 注入，禁止自行 new session；生成逻辑在 Celery 任务内（红线 4）。
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ReportNotFound
from app.common.pagination import parse_pagination
from app.models.report import REPORT_STATUS_PENDING, Report
from app.schemas.report import DimensionScore, QuestionScore, ReportDetail, ReportListItem

logger = logging.getLogger(__name__)


def _str_list(payload: dict, key: str) -> list[str]:
    """从 JSONB payload 取字符串数组，空值兜底（§7.2）。"""
    value = payload.get(key)
    return [str(x) for x in value] if isinstance(value, list) else []


class ReportService:
    @staticmethod
    async def _get_by_interview(db: AsyncSession, interview_id: int) -> Report | None:
        stmt = select(Report).where(
            Report.interview_id == interview_id, Report.deleted_at.is_(None)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def create_pending(
        db: AsyncSession, *, interview_id: int, user_id: int, prompt_version: str
    ) -> Report:
        """创建 pending 报告行（幂等：同一 interview_id 已存在则直接返回，不重复建行）。"""
        existing = await ReportService._get_by_interview(db, interview_id)
        if existing is not None:
            return existing
        report = Report(
            interview_id=interview_id,
            user_id=user_id,
            status=REPORT_STATUS_PENDING,
            prompt_version=prompt_version,
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        logger.info("report pending created report_id=%s interview_id=%s", report.id, interview_id)
        return report

    @staticmethod
    def enqueue(report_id: int) -> str:
        """下发报告生成任务，返回 Celery task_id（延迟导入避免循环依赖）。"""
        from app.tasks.report import generate_report_task

        result = generate_report_task.delay(report_id=report_id)
        return str(getattr(result, "id", "") or "")

    @staticmethod
    def enqueue_pdf(report_id: int) -> str:
        """下发 PDF 渲染任务，返回 Celery task_id（延迟导入避免循环依赖）。"""
        from app.tasks.report import export_report_pdf_task

        result = export_report_pdf_task.delay(report_id=report_id)
        return str(getattr(result, "id", "") or "")

    @staticmethod
    async def get(db: AsyncSession, *, user_id: int, report_id: int) -> Report:
        report = await db.get(Report, report_id)
        if report is None or report.deleted_at is not None or report.user_id != user_id:
            raise ReportNotFound()  # 归属不符不返回 403，避免暴露资源存在性（§11.3）
        return report

    @staticmethod
    async def get_by_interview(db: AsyncSession, *, user_id: int, interview_id: int) -> Report | None:
        report = await ReportService._get_by_interview(db, interview_id)
        if report is None or report.user_id != user_id:
            return None
        return report

    @staticmethod
    async def list(
        db: AsyncSession, *, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[int, list[Report]]:
        page, page_size = parse_pagination(page, page_size)
        cond = (Report.user_id == user_id, Report.deleted_at.is_(None))
        total = (await db.execute(select(func.count()).select_from(Report).where(*cond))).scalar_one()
        stmt = (
            select(Report)
            .where(*cond)
            .order_by(Report.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await db.execute(stmt)).scalars().all())
        return int(total), items

    @staticmethod
    def build_detail(report: Report) -> ReportDetail:
        """从 ORM 行组装 ReportDetail（JSONB 空值兜底，§7.2）。"""
        payload = report.payload_json if isinstance(report.payload_json, dict) else {}
        dims_raw = payload.get("dimensions")
        if not isinstance(dims_raw, list):
            dims_raw = report.dimensions_json if isinstance(report.dimensions_json, list) else []
        question_scores_raw = payload.get("question_scores")
        if not isinstance(question_scores_raw, list):
            question_scores_raw = []
        return ReportDetail(
            report_id=report.id,
            interview_id=report.interview_id,
            status=report.status,
            prompt_version=report.prompt_version,
            overall_score=float(report.overall_score) if report.overall_score is not None else None,
            grade=report.grade,
            summary=payload.get("summary"),
            dimensions=[DimensionScore.model_validate(d) for d in dims_raw if isinstance(d, dict)],
            strengths=_str_list(payload, "strengths"),
            weaknesses=_str_list(payload, "weaknesses"),
            suggestions=_str_list(payload, "suggestions"),
            hire_recommendation=payload.get("hire_recommendation"),
            question_scores=[QuestionScore.model_validate(q) for q in question_scores_raw if isinstance(q, dict)],
            answer_quality_avg=payload.get("answer_quality_avg"),
            pdf_ready=bool(report.pdf_object_key),
            pdf_error_message=report.pdf_error_message,
            error_message=report.error_message,
            generated_at=report.generated_at.isoformat() if report.generated_at else None,
        )

    @staticmethod
    def build_list_item(report: Report) -> ReportListItem:
        return ReportListItem(
            report_id=report.id,
            interview_id=report.interview_id,
            status=report.status,
            overall_score=float(report.overall_score) if report.overall_score is not None else None,
            grade=report.grade,
            generated_at=report.generated_at.isoformat() if report.generated_at else None,
        )
