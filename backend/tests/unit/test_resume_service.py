"""services/resume/service 单测：归属校验 / 列表分页 / 创建 pending 记录。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.common.exceptions import ResumeForbidden, ResumeNotFound
from app.services.resume.service import ResumeService
from tests.fakes import FakeSession, make_resume


def run(coro):
    return asyncio.run(coro)


def test_get_returns_owned_resume():
    resume = make_resume(resume_id=1, user_id=1)
    session = FakeSession().configure(get_map={1: resume})
    result = run(ResumeService.get(session, user_id=1, resume_id=1))
    assert result.id == 1


def test_get_forbidden_for_other_user():
    resume = make_resume(resume_id=1, user_id=2)
    session = FakeSession().configure(get_map={1: resume})
    with pytest.raises(ResumeForbidden):
        run(ResumeService.get(session, user_id=1, resume_id=1))


def test_get_not_found():
    session = FakeSession().configure(get_map={})
    with pytest.raises(ResumeNotFound):
        run(ResumeService.get(session, user_id=1, resume_id=999))


def test_create_pending_and_enqueue(monkeypatch):
    session = FakeSession()
    fake_task = SimpleNamespace(delay=lambda **kw: SimpleNamespace(id="task-1"))
    monkeypatch.setattr("app.tasks.resume_parser.parse_resume_task", fake_task)
    resume = run(ResumeService.create(
        session, user_id=1, object_key="resumes/1_x.pdf", original_ext="pdf", size_bytes=10, mime_type="application/pdf"
    ))
    assert resume.status == "pending"
    assert resume.id == 1
    assert ResumeService.enqueue(resume.id) == "task-1"


def test_list_returns_total_and_items():
    r1, r2 = make_resume(resume_id=1), make_resume(resume_id=2)
    session = FakeSession().configure(scalar_one=2, scalars=[r1, r2])
    total, items = run(ResumeService.list(session, user_id=1, page=1, page_size=20))
    assert total == 2
    assert len(items) == 2
