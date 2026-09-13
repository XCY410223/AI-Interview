"""简历模块 schema：上传/状态查询 + 解析结果冻结契约（规范 §6.2 / M1 计划 §4.4/§5.4）。"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMModel

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---- 上传 / 状态查询 ----
class UploadResponse(BaseModel):
    id: int
    status: str
    task_id: str | None = None
    uploaded_at: datetime


class ResumeStatusResponse(BaseModel):
    id: int
    status: str
    original_ext: str | None = None
    parsed_content: dict | None = None
    error_message: str | None = None
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None


class ResumeListItem(ORMModel):
    id: int
    status: str
    original_ext: str
    size_bytes: int
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None


# ---- 解析结果（冻结契约，§5.4；先冻结 schema 再写 service）----
class PersonalInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v


class EducationItem(BaseModel):
    school: str
    major: str | None = None
    degree: str | None = None
    start: str | None = None
    end: str | None = None


class ProjectItem(BaseModel):
    name: str
    role: str | None = None
    description: str
    tech_stack: list[str] = Field(default_factory=list)


class ParsedResume(BaseModel):
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    summary: str = ""
