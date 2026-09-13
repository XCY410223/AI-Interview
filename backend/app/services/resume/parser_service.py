"""简历文本提取 + LLM 结构化解析（规范 §9.3/§10.1 / M1 计划 §5）。

- 提取：pdfplumber（PDF）/ python-docx（DOCX）抽文本；
- 解析：走统一 LLM 客户端（红线 6），JSON 模式 + Pydantic 校验（红线 5）；
- 失败兜底：LLM 失败 / Pydantic 校验失败统一抛 AIClientError（可重试），绝不直接 500。
"""
from __future__ import annotations

import io
import logging

import docx
import pdfplumber

from app.common.exceptions import AIClientError, ResumeFileCorrupted
from app.core.llm.client import LLMError, llm_client
from app.prompts.resume_parser import get_prompt
from app.schemas.resume import ParsedResume

logger = logging.getLogger(__name__)


def extract_text(content: bytes, ext: str) -> str:
    """按扩展名抽取纯文本。失败抛 ResumeFileCorrupted（不可重试）。"""
    ext = (ext or "").lower()
    if ext == "pdf":
        return _extract_pdf(content)
    if ext == "docx":
        return _extract_docx(content)
    raise ResumeFileCorrupted(f"unsupported extension: {ext}")


def _extract_pdf(content: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages).strip()
    except Exception as exc:
        raise ResumeFileCorrupted(f"pdf extraction failed: {exc}") from exc


def _extract_docx(content: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs).strip()
    except Exception as exc:
        raise ResumeFileCorrupted(f"docx extraction failed: {exc}") from exc


async def parse_text(text: str) -> ParsedResume:
    """调用统一 LLM 客户端解析简历文本为结构化 ParsedResume。

    系统指令（Prompt）与用户输入（简历文本）分层（§9.4 注入防护）。
    LLM 失败 / 返回非法 JSON / Pydantic 校验失败 → AIClientError（可重试）。
    """
    if not text or not text.strip():
        raise ResumeFileCorrupted("简历文本为空")

    messages = [
        {"role": "system", "content": get_prompt()},
        {"role": "user", "content": text},
    ]
    try:
        result = await llm_client.chat(messages, json_mode=True)
    except LLMError as exc:
        raise AIClientError(str(exc)) from exc

    data = result.data or {}
    try:
        return ParsedResume.model_validate(data)
    except Exception as exc:
        raise AIClientError(f"parsed resume validation failed: {exc}") from exc
