"""报告生成 / PDF 导出 Celery 任务（幂等 + 状态回写，规范 §10.2 / M3 计划 §六）。

- report.generate：聚合问答 → LLM 结构化输出 → 校验 → 落库 → 链式投递 PDF；
- report.export_pdf：渲染 HTML → WeasyPrint → 存 MinIO → 写 pdf_object_key。

与 resume_parser.py 同构：@shared_task(bind=True, name=...) + 独立 _run() 便于注入 fake 单测。
WeasyPrint 延迟导入：本地单测/CI 无 Pango 系统库时仍可 import 本模块。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

from app.core.database import async_session_factory
from app.core.llm.client import LLMError, llm_client
from app.core.redis import build_redis
from app.core.storage import StorageClient, get_storage
from app.models.report import (
    REPORT_STATUS_COMPLETED,
    REPORT_STATUS_FAILED,
    REPORT_STATUS_PENDING,
    REPORT_STATUS_PROCESSING,
    Report,
)
from app.prompts.report import get_prompt
from app.schemas.report import ReportPayload
from app.services.interview.service import InterviewContext, InterviewService
from app.services.report.cache import release_gen_lock, set_payload
from app.services.report.pdf_template import render_report_html
from app.services.report.service import ReportService

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
PDF_OBJECT_KEY_PREFIX = "reports"
_MAX_TRANSCRIPT_TURNS = 20
_MAX_ANSWER_CHARS = 2000


@shared_task(
    bind=True,
    name="report.generate",
    max_retries=MAX_RETRIES,
    default_retry_delay=15,
    retry_backoff=True,
    retry_jitter=True,
    time_limit=300,
    soft_time_limit=270,
)
def generate_report_task(self, report_id: int) -> dict:
    return asyncio.run(_run_generate(report_id, task=self))


@shared_task(
    bind=True,
    name="report.export_pdf",
    max_retries=2,
    default_retry_delay=15,
    retry_backoff=True,
    retry_jitter=True,
    time_limit=120,
    soft_time_limit=100,
)
def export_report_pdf_task(self, report_id: int) -> dict:
    return asyncio.run(_run_export_pdf(report_id, task=self))


# ---------------------------------------------------------------------------
# report.generate
# ---------------------------------------------------------------------------
def _build_transcript(context: InterviewContext) -> str:
    turns = context.turns[:_MAX_TRANSCRIPT_TURNS]
    if not turns:
        return "（无问答记录）"
    parts: list[str] = []
    for t in turns:
        answer = t.answer if len(t.answer) <= _MAX_ANSWER_CHARS else t.answer[:_MAX_ANSWER_CHARS] + "…"
        score = f"{t.score:.1f}" if t.score is not None else "—"
        parts.append(
            f"第 {t.question_index + 1} 题·第 {t.round + 1} 轮\n"
            f"问：{t.question}\n答：{answer}\n评分：{score}"
        )
    return "\n\n".join(parts)


def _answer_quality_hint(avg: float | None) -> str:
    if avg is None:
        return "（无逐题评分数据）"
    return f"逐题四维评分均值约 {avg:.1f} 分，供能力评定参考，避免能力评分与逐题评分自相矛盾。"


async def _run_generate(
    report_id: int,
    *,
    task=None,
    session_factory=async_session_factory,
    redis_factory=build_redis,
) -> dict:
    # 1. 读取 report：not_found / 幂等短路 / 置 processing（独立 session，事务边界在任务内）
    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return {"status": "not_found", "report_id": report_id}
        if report.status == REPORT_STATUS_COMPLETED:
            return {"status": "skipped", "report_id": report_id}
        interview_id = report.interview_id
        user_id = report.user_id
        report.status = REPORT_STATUS_PROCESSING
        await db.commit()

    try:
        # 2. 面试上下文（跨模块只读契约）
        async with session_factory() as db:
            context = await InterviewService.load_for_report(
                db, interview_id=interview_id, user_id=user_id
            )
        if context is None:
            raise ValueError("面试上下文不可用（不存在/已删除/归属不符）")

        # 3. 组装 transcript + 分层消息（候选人内容只进 user 段，§9.4）
        transcript = _build_transcript(context)
        prompt = get_prompt()
        system = prompt.format(
            position=context.position,
            difficulty=context.difficulty,
            style=context.style,
            question_count=len(context.questions),
            resume_summary=context.resume_summary or "（无简历信息）",
            transcript=transcript,
            answer_quality_hint=_answer_quality_hint(context.answer_quality_avg),
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": transcript}]

        # 4. LLM 结构化输出 + Pydantic 校验（红线 5/6：json_mode + 统一客户端，禁正则抠 JSON）
        result = await llm_client.chat(messages, json_mode=True)
        payload = ReportPayload.model_validate(result.data or {})
    except (LLMError, ValueError) as exc:
        # 可重试异常：LLM 不可用 / 结构化输出校验失败 → retry_count+1，耗尽转 failed
        exhausted = await _handle_retry(session_factory, report_id, exc)
        if exhausted:
            return {"status": "failed", "report_id": report_id, "error": str(exc)}
        if task is not None:
            raise task.retry(exc=exc)
        raise exc
    except Exception as exc:
        await _mark_failed(session_factory, report_id, str(exc))
        raise

    # 5. 落库：总分/等级/维度/产物均由服务端算（不接受 LLM 自报总分）
    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return {"status": "not_found", "report_id": report_id}
        payload_dict = payload.model_dump()
        payload_dict["answer_quality_avg"] = context.answer_quality_avg
        report.dimensions_json = [d.model_dump() for d in payload.dimensions]
        report.payload_json = payload_dict
        report.overall_score = payload.overall_score
        report.grade = payload.grade
        report.generated_at = datetime.now(timezone.utc)
        report.error_message = None
        report.status = REPORT_STATUS_COMPLETED
        await db.commit()
        detail = ReportService.build_detail(report)

    # 6. 释放生成锁 + 回填结果缓存（best-effort，失败不影响主流程）
    await _release_lock_and_cache(redis_factory, user_id, interview_id, report_id, detail)

    # 7. 链式投递 PDF（报告生成完即预热，用户点导出秒回）
    export_report_pdf_task.delay(report_id=report_id)
    logger.info("report generated report_id=%s interview_id=%s", report_id, interview_id)
    return {"status": "completed", "report_id": report_id}


async def _release_lock_and_cache(redis_factory, user_id: int, interview_id: int, report_id: int, detail) -> None:
    redis = redis_factory()
    try:
        await release_gen_lock(redis, interview_id)
        await set_payload(redis, user_id, report_id, detail.model_dump(mode="json"))
    except Exception:  # pragma: no cover - Redis 抖动不应阻塞报告主流程
        logger.warning("报告缓存/锁清理失败 report_id=%s", report_id, exc_info=True)
    finally:
        await redis.aclose()


async def _handle_retry(session_factory, report_id: int, exc: Exception) -> bool:
    """瞬时错误：retry_count+1；耗尽 → failed（返回 True），否则回 pending（返回 False）。"""
    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return True
        report.retry_count += 1
        if report.retry_count > MAX_RETRIES:
            report.status = REPORT_STATUS_FAILED
            report.error_message = str(exc)
            await db.commit()
            return True
        report.status = REPORT_STATUS_PENDING
        await db.commit()
        return False


async def _mark_failed(session_factory, report_id: int, message: str) -> None:
    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is not None:
            report.status = REPORT_STATUS_FAILED
            report.error_message = message
            await db.commit()


# ---------------------------------------------------------------------------
# report.export_pdf
# ---------------------------------------------------------------------------
def _render_pdf(html: str) -> bytes:
    from weasyprint import HTML  # 延迟导入：无 Pango 系统库的环境仍可 import 本模块

    return HTML(string=html).write_pdf()


async def _run_export_pdf(
    report_id: int,
    *,
    task=None,
    session_factory=async_session_factory,
    storage: StorageClient | None = None,
) -> dict:
    storage = storage or get_storage()

    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return {"status": "not_found", "report_id": report_id}
        if report.status != REPORT_STATUS_COMPLETED:
            return {"status": "not_ready", "report_id": report_id}
        if report.pdf_object_key:
            return {"status": "skipped", "report_id": report_id}  # 产物已存在，幂等
        detail = ReportService.build_detail(report)

    object_key = f"{PDF_OBJECT_KEY_PREFIX}/{report_id}.pdf"
    try:
        # 渲染 + 上传放同一 try：WeasyPrint 缺系统库 / MinIO 抖动都按瞬时错误处理
        pdf_bytes = _render_pdf(render_report_html(detail))
        await storage.put_object(object_key, pdf_bytes, "application/pdf")
    except Exception as exc:
        logger.warning("report pdf export failed report_id=%s: %s", report_id, exc)
        if task is not None and task.request.retries < task.max_retries:
            raise task.retry(exc=exc)
        # 重试耗尽 / 无 task（单测直调）：回写失败原因，供前端明确提示（不再静默）
        await _mark_pdf_failed(session_factory, report_id, str(exc))
        if task is not None:
            return {"status": "failed", "report_id": report_id, "error": str(exc)}
        raise

    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is None:
            return {"status": "not_found", "report_id": report_id}
        report.pdf_object_key = object_key
        report.pdf_generated_at = datetime.now(timezone.utc)
        report.pdf_error_message = None
        await db.commit()

    logger.info("report pdf exported report_id=%s object_key=%s", report_id, object_key)
    return {"status": "completed", "report_id": report_id, "object_key": object_key}


async def _mark_pdf_failed(session_factory, report_id: int, message: str) -> None:
    """PDF 导出永久失败：回写失败原因（报告本身已完成，不影响 status）。"""
    async with session_factory() as db:
        report = await db.get(Report, report_id)
        if report is not None:
            report.pdf_error_message = message
            await db.commit()
