"""题库路由：JD 解析、真题 RAG 检索与入库、模板 CRUD（M4 计划 §四）。

红线 1：注册前已 grep `question_bank.router`，仅在本文件定义，registry 统一挂载 `/question-bank`。
红线 4/6：JD 解析为交互式单次 LLM 调用（M4 决策 D1），同步返回，计入 AI 限流；
          入库管线走 Celery 异步（红线 4 范围外，见 tasks/rag.py）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.question_bank import (
    IngestRequest,
    IngestResponse,
    JDParseRequest,
    JDParseResponse,
    QuestionBankSearchResponse,
    QuestionTemplateCreate,
    QuestionTemplateOut,
    QuestionTemplateUpdate,
)
from app.services.common.ai_rate_limit import charge_ai_request
from app.services.question_bank import retrieval
from app.services.question_bank.jd_service import parse_jd
from app.services.question_bank.service import QuestionBankService
from app.services.question_bank.template_service import TemplateService

router = APIRouter()


@router.post("/jd/parse", response_model=JDParseResponse)
async def parse_jd_endpoint(
    payload: JDParseRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """JD 解析（同步，D1）：贴入 JD 原文 → 返回岗位名 + 能力项清单。计入 AI 限流防刷。"""
    await charge_ai_request(redis, current_user.id)
    return await parse_jd(payload.jd_text)


@router.post("/ingest", status_code=202, response_model=IngestResponse)
async def ingest_endpoint(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """面经入库（文本粘贴，D6）：建作业行 → 下发 Celery 切片/去重/embedding 任务（红线 4）。"""
    item = await QuestionBankService.create_ingest(
        db,
        user_id=current_user.id,
        company=payload.company,
        position=payload.position,
        difficulty=payload.difficulty,
        content=payload.content,
        source_url=payload.source_url,
    )
    task_id = QuestionBankService.enqueue(item.id)
    return JSONResponse(
        status_code=202,
        content=IngestResponse(item_id=item.id, status=item.status, task_id=task_id).model_dump(),
    )


@router.get("/search", response_model=QuestionBankSearchResponse)
async def search_endpoint(
    company: str,
    position: str,
    difficulty: str = "medium",
    top_k: int = 8,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """真题检索（调试/回显，带缓存）：按公司+岗位+难度 cosine top-K。"""
    # 入参经 Query 参数直接校验，缺省走 schema 语义；top_k 夹取 1~32
    top_k = max(1, min(top_k, 32))
    items = await retrieval.search(
        db,
        company=company,
        position=position,
        difficulty=difficulty,
        top_k=top_k,
        redis=redis,
    )
    return QuestionBankSearchResponse(items=items)


# ---- 题库模板 CRUD（M4 PR-R7-a：全局共享沉淀，低频管理功能）----
@router.post("/templates", status_code=201, response_model=QuestionTemplateOut)
async def create_template(
    payload: QuestionTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await TemplateService.create(
        db,
        position=payload.position,
        difficulty=payload.difficulty,
        category=payload.category,
        content=payload.content,
        reference_points=payload.reference_points,
        tags=payload.tags,
    )
    return QuestionTemplateOut.model_validate(template)


@router.get("/templates", response_model=dict)
async def list_templates(
    page: int = 1,
    page_size: int = 20,
    position: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = await TemplateService.list_templates(db, page=page, page_size=page_size, position=position)
    return {"total": total, "items": [QuestionTemplateOut.model_validate(t) for t in items]}


@router.get("/templates/{template_id}", response_model=QuestionTemplateOut)
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await TemplateService.get(db, template_id=template_id)
    return QuestionTemplateOut.model_validate(template)


@router.put("/templates/{template_id}", response_model=QuestionTemplateOut)
async def update_template(
    template_id: int,
    payload: QuestionTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await TemplateService.get(db, template_id=template_id)
    template = await TemplateService.update(
        db,
        template=template,
        position=payload.position,
        difficulty=payload.difficulty,
        category=payload.category,
        content=payload.content,
        reference_points=payload.reference_points,
        tags=payload.tags,
    )
    return QuestionTemplateOut.model_validate(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await TemplateService.get(db, template_id=template_id)
    await TemplateService.delete(db, template=template)
    return None
