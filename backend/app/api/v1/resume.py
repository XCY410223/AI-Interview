"""简历路由：上传、状态查询、结构化展示（M1 计划 §4.4）。"""
from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.common.exceptions import ResumeFileTooLarge
from app.common.filename import MAX_FILE_SIZE_BYTES
from app.core.storage import get_storage
from app.models.user import User
from app.schemas.resume import ResumeListItem, ResumeStatusResponse, UploadResponse
from app.services.resume.service import ResumeService
from app.services.resume.storage_service import ResumeStorageService

router = APIRouter()


@router.post("/upload", status_code=201, response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 大小限制（§4.4：Nginx 12m + 应用层 10MB 二次校验）
    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ResumeFileTooLarge()

    filename = file.filename or ""
    mime = file.content_type or ""
    ext = PurePosixPath(filename.replace("\x00", "")).suffix.lstrip(".").lower()

    storage = get_storage()
    object_key = await ResumeStorageService.upload(
        storage, user_id=current_user.id, filename=filename, mime=mime, content=content
    )
    resume = await ResumeService.create(
        db,
        user_id=current_user.id,
        object_key=object_key,
        original_ext=ext,
        size_bytes=len(content),
        mime_type=mime,
    )
    task_id = ResumeService.enqueue(resume.id)
    return {
        "id": resume.id,
        "status": resume.status,
        "task_id": task_id,
        "uploaded_at": resume.uploaded_at,
    }


@router.get("/{resume_id}", response_model=ResumeStatusResponse)
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resume = await ResumeService.get(db, user_id=current_user.id, resume_id=resume_id)
    return {
        "id": resume.id,
        "status": resume.status,
        "original_ext": resume.original_ext,
        "parsed_content": resume.parsed_content,
        "error_message": resume.error_message,
        "uploaded_at": resume.uploaded_at,
        "processed_at": resume.processed_at,
    }


@router.get("", response_model=dict)
async def list_resumes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = await ResumeService.list(db, user_id=current_user.id, page=page, page_size=page_size)
    return {
        "total": total,
        "items": [ResumeListItem.model_validate(r) for r in items],
    }
