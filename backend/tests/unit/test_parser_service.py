"""services/resume/parser_service 单测：文本提取（PDF/DOCX）与 LLM 解析（mock LLM）。"""
from __future__ import annotations

import asyncio
import io

import pytest
from docx import Document

from app.common.exceptions import AIClientError, ResumeFileCorrupted
from app.core.llm.client import LLMError
from app.schemas.resume import ParsedResume
from app.services.resume.parser_service import extract_text, parse_text


def run(coro):
    return asyncio.run(coro)


# ---- 文本提取 ----
def test_extract_docx_success():
    doc = Document()
    doc.add_paragraph("Hello World")
    buf = io.BytesIO()
    doc.save(buf)
    text = extract_text(buf.getvalue(), "docx")
    assert "Hello World" in text


def _make_minimal_pdf(text: str = "Hello PDF") -> bytes:
    content = f"BT /F1 24 Tf 100 700 Td ({text}) Tj ET".encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def test_extract_pdf_success():
    text = extract_text(_make_minimal_pdf("Hello PDF"), "pdf")
    assert "Hello PDF" in text


def test_extract_pdf_corrupted_raises():
    with pytest.raises(ResumeFileCorrupted):
        extract_text(b"not a pdf at all", "pdf")


def test_extract_unsupported_ext_raises():
    with pytest.raises(ResumeFileCorrupted):
        extract_text(b"x", "txt")


# ---- LLM 解析（mock 统一客户端）----
class _FakeClient:
    def __init__(self, data=None, exc=None):
        self._data = data
        self._exc = exc
        self.calls: list = []

    async def chat(self, messages, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if self._exc is not None:
            raise self._exc
        result = type("R", (), {})()
        result.data = self._data
        return result


def test_parse_text_success_and_message_layering(monkeypatch):
    client = _FakeClient(data={
        "personal": {"name": "张三"},
        "education": [], "projects": [], "skills": ["Python"], "summary": "概述",
    })
    monkeypatch.setattr("app.services.resume.parser_service.llm_client", client)
    parsed = run(parse_text("简历文本"))
    assert isinstance(parsed, ParsedResume)
    assert parsed.personal.name == "张三"
    # 系统指令与用户输入分层（§9.4 注入防护）
    assert client.calls[0]["json_mode"] is True
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert client.calls[0]["messages"][1]["role"] == "user"
    assert client.calls[0]["messages"][1]["content"] == "简历文本"


def test_parse_text_llm_error_raises_aiclient(monkeypatch):
    monkeypatch.setattr("app.services.resume.parser_service.llm_client", _FakeClient(exc=LLMError("boom")))
    with pytest.raises(AIClientError):
        run(parse_text("文本"))


def test_parse_text_invalid_schema_raises_aiclient(monkeypatch):
    monkeypatch.setattr("app.services.resume.parser_service.llm_client", _FakeClient(data={"education": "not-a-list"}))
    with pytest.raises(AIClientError):
        run(parse_text("文本"))


def test_parse_text_empty_raises_corrupted():
    with pytest.raises(ResumeFileCorrupted):
        run(parse_text(""))
