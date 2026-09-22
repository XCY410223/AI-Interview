"""报告路由：生成、查询、导出 PDF（M3 计划 §七）。

归属权校验：每个接口都过 get_current_user 且校验 report.user_id == current_user.id，
违者 404（不返回 403，避免暴露资源存在性，§11.3）。面试归属经 InterviewService 只读入口校验（§3.1）。
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.common.exceptions import InterviewNotFinished, ReportNotFound, ReportNotReady
from app.core.storage import get_storage
from app.models.interview import INTERVIEW_STATUS_COMPLETED
from app.models.report import REPORT_STATUS_COMPLETED, REPORT_STATUS_PENDING, REPORT_STATUS_PROCESSING
from app.models.user import User
from app.prompts.report import CURRENT_VERSION as REPORT_PROMPT_VERSION
from app.schemas.report import CreateReportRequest, CreateReportResponse, ReportDetail
from app.services.interview.service import InterviewService
from app.services.report.cache import acquire_gen_lock, get_payload, set_payload
from app.services.report.service import ReportService

router = APIRouter()


def _existing_response(report) -> CreateReportResponse:
    return CreateReportResponse(report_id=report.id, status=report.status)


@router.post("", response_model=CreateReportResponse)
async def create_report(
    payload: CreateReportRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """生成/重新生成报告：校验面试完成 → 幂等返回或入队。"""
    interview = await InterviewService.get_owned_or_none(
        db, user_id=current_user.id, interview_id=payload.interview_id
    )
    if interview is None:
        raise ReportNotFound("面试不存在或无权访问")
    if interview.status != INTERVIEW_STATUS_COMPLETED:
        raise InterviewNotFinished()

    existing = await ReportService.get_by_interview(
        db, user_id=current_user.id, interview_id=payload.interview_id
    )
    if existing is not None and existing.status in (
        REPORT_STATUS_PENDING,
        REPORT_STATUS_PROCESSING,
        REPORT_STATUS_COMPLETED,
    ):
        return _existing_response(existing)  # 幂等：进行中/已完成不重复入队（防重复计费）

    # 不存在或 failed：拿生成锁 → 建行/复位 → 入队
    if not await acquire_gen_lock(redis, payload.interview_id):
        raise ReportNotReady("报告生成中，请稍后查看")

    if existing is not None:  # failed → 复位重生成
        existing.status = REPORT_STATUS_PENDING
        existing.retry_count = 0
        existing.error_message = None
        await db.commit()
        report = existing
    else:
        report = await ReportService.create_pending(
            db,
            interview_id=payload.interview_id,
            user_id=current_user.id,
            prompt_version=REPORT_PROMPT_VERSION,
        )
    ReportService.enqueue(report.id)
    return JSONResponse(
        status_code=202,
        content=CreateReportResponse(report_id=report.id, status=report.status).model_dump(),
    )


@router.get("", response_model=dict)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = await ReportService.list(db, user_id=current_user.id, page=page, page_size=page_size)
    return {
        "total": total,
        "items": [ReportService.build_list_item(r) for r in items],
    }


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """报告详情：先读结果缓存（key 含 user_id，防越权），miss 查 DB 后回填。"""
    cached = await get_payload(redis, current_user.id, report_id)
    if cached is not None:
        return cached
    report = await ReportService.get(db, user_id=current_user.id, report_id=report_id)
    detail = ReportService.build_detail(report)
    await set_payload(redis, current_user.id, report_id, detail.model_dump(mode="json"))
    return detail


@router.post("/{report_id}/pdf", response_model=CreateReportResponse)
async def export_pdf(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发 PDF 渲染入队（幂等：已导出直接返回）。"""
    report = await ReportService.get(db, user_id=current_user.id, report_id=report_id)
    if report.status != REPORT_STATUS_COMPLETED:
        raise ReportNotReady("报告尚未生成完成")
    if report.pdf_object_key:
        return CreateReportResponse(report_id=report_id, status="completed")
    ReportService.enqueue_pdf(report_id)
    return JSONResponse(
        status_code=202,
        content=CreateReportResponse(report_id=report_id, status="processing").model_dump(),
    )


@router.get("/{report_id}/pdf")
async def download_pdf(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """下载 PDF：归属校验后从对象存储流式回源（红线 8，禁止本地磁盘）。"""
    report = await ReportService.get(db, user_id=current_user.id, report_id=report_id)
    if report.status != REPORT_STATUS_COMPLETED:
        raise ReportNotReady("报告尚未生成完成")
    if not report.pdf_object_key:
        raise ReportNotReady("PDF 尚未生成，请稍后重试")

    pdf_bytes = await get_storage().get_object(report.pdf_object_key)
    filename = f"面试评估报告_{report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
