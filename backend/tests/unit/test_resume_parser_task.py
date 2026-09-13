"""tasks/resume_parser 单测：状态机（mock LLM / storage / session，M1 计划 §5.6）。"""
from __future__ import annotations

import asyncio

import pytest

from app.common.exceptions import AIClientError
from app.schemas.resume import ParsedResume
from app.tasks.resume_parser import _run
from tests.fakes import FakeSession, FakeStorage, make_resume


def run(coro):
    return asyncio.run(coro)


class _RetrySentinel(Exception):
    pass


class _FakeTask:
    def __init__(self):
        self.retry_calls = 0

    def retry(self, exc=None):
        self.retry_calls += 1
        raise _RetrySentinel()


def _patch_parser(monkeypatch, *, parsed=None, error=None):
    monkeypatch.setattr("app.tasks.resume_parser.extract_text", lambda content, ext: "text")

    async def fake_parse(text):
        if error is not None:
            raise error
        return parsed

    monkeypatch.setattr("app.tasks.resume_parser.parse_text", fake_parse)


def test_run_success_writes_completed(monkeypatch):
    resume = make_resume(resume_id=1, status="pending")
    session = FakeSession().configure(get_map={1: resume})
    storage = FakeStorage({"resumes/1_abc.pdf": b"fake"})
    parsed = ParsedResume(personal={"name": "张三"})
    _patch_parser(monkeypatch, parsed=parsed)

    result = run(_run(1, session_factory=lambda: session, storage=storage))

    assert result["status"] == "completed"
    assert resume.status == "completed"
    assert resume.parsed_content == parsed.model_dump()


def test_run_skips_completed(monkeypatch):
    resume = make_resume(resume_id=1, status="completed")
    session = FakeSession().configure(get_map={1: resume})
    result = run(_run(1, session_factory=lambda: session, storage=FakeStorage()))
    assert result["status"] == "skipped"


def test_run_not_found():
    session = FakeSession().configure(get_map={})
    result = run(_run(1, session_factory=lambda: session, storage=FakeStorage()))
    assert result["status"] == "not_found"


def test_run_transient_error_retries_and_bumps_count(monkeypatch):
    resume = make_resume(resume_id=1, status="pending")
    session = FakeSession().configure(get_map={1: resume})
    storage = FakeStorage({"resumes/1_abc.pdf": b"fake"})
    _patch_parser(monkeypatch, error=AIClientError("boom"))
    task = _FakeTask()

    with pytest.raises(_RetrySentinel):
        run(_run(1, task=task, session_factory=lambda: session, storage=storage))

    assert task.retry_calls == 1
    assert resume.retry_count == 1
    assert resume.status == "pending"


def test_run_retry_exhausted_marks_failed(monkeypatch):
    resume = make_resume(resume_id=1, status="pending", retry_count=3)
    session = FakeSession().configure(get_map={1: resume})
    storage = FakeStorage({"resumes/1_abc.pdf": b"fake"})
    _patch_parser(monkeypatch, error=AIClientError("boom"))

    result = run(_run(1, session_factory=lambda: session, storage=storage))

    assert result["status"] == "failed"
    assert resume.status == "failed"
    assert resume.retry_count == 4
    assert resume.error_message


def test_run_missing_storage_marks_failed_and_raises(monkeypatch):
    resume = make_resume(resume_id=1, status="pending")
    session = FakeSession().configure(get_map={1: resume})
    _patch_parser(monkeypatch, parsed=ParsedResume())

    with pytest.raises(FileNotFoundError):
        run(_run(1, session_factory=lambda: session, storage=FakeStorage()))

    assert resume.status == "failed"
