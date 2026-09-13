"""简历 API 集成测试（TestClient + 内存 fakes，M1 计划 §4.5）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1 import deps
from app.main import app
from tests.fakes import FakeStorage, make_resume, make_user

PDF = b"%PDF-1.4 fake content"


@pytest.fixture
def resume_client(client, monkeypatch):
    state = client.state
    state["storage"] = FakeStorage()
    state["user"] = make_user(user_id=1)

    async def get_current_user_override():
        return state["user"]

    app.dependency_overrides[deps.get_current_user] = get_current_user_override
    monkeypatch.setattr("app.api.v1.resume.get_storage", lambda: state["storage"])
    return client


def _fake_task(monkeypatch):
    fake = SimpleNamespace(delay=lambda **kw: SimpleNamespace(id="task-1"))
    monkeypatch.setattr("app.tasks.resume_parser.parse_resume_task", fake)


def test_upload_success(resume_client, monkeypatch):
    _fake_task(monkeypatch)
    resp = resume_client.post(
        "/api/v1/resumes/upload", files={"file": ("简历.pdf", PDF, "application/pdf")}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["task_id"] == "task-1"
    # object_key 不含原始文件名（红线 3）
    keys = list(resume_client.state["storage"].objects.keys())
    assert len(keys) == 1
    assert "简历" not in keys[0]
    assert keys[0].startswith("resumes/1_") and keys[0].endswith(".pdf")


def test_upload_exe_rejected(resume_client, monkeypatch):
    _fake_task(monkeypatch)
    resp = resume_client.post(
        "/api/v1/resumes/upload", files={"file": ("file.exe", b"x", "application/pdf")}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESUME_INVALID_EXTENSION"


def test_upload_mime_forgery_rejected(resume_client, monkeypatch):
    _fake_task(monkeypatch)
    resp = resume_client.post(
        "/api/v1/resumes/upload", files={"file": ("file.pdf", PDF, "text/plain")}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESUME_INVALID_MIME"


def test_upload_too_large_413(resume_client):
    big = b"x" * (11 * 1024 * 1024)
    resp = resume_client.post(
        "/api/v1/resumes/upload", files={"file": ("file.pdf", big, "application/pdf")}
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "RESUME_FILE_TOO_LARGE"


def test_upload_requires_auth(client):
    resp = client.post("/api/v1/resumes/upload", files={"file": ("file.pdf", PDF, "application/pdf")})
    assert resp.status_code == 401


def test_get_resume_forbidden_for_other_user(resume_client):
    resume = make_resume(resume_id=1, user_id=2)  # 属于用户 2
    resume_client.state["db"].configure(get_map={1: resume})
    resp = resume_client.get("/api/v1/resumes/1")
    assert resp.status_code == 403
    assert resp.json()["code"] == "RESUME_FORBIDDEN"


def test_get_resume_not_found(resume_client):
    resume_client.state["db"].configure(get_map={})
    resp = resume_client.get("/api/v1/resumes/999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "RESUME_NOT_FOUND"


def test_get_resume_success(resume_client):
    resume = make_resume(resume_id=1, user_id=1, status="completed")
    resume.parsed_content = {"personal": {"name": "张三"}}
    resume_client.state["db"].configure(get_map={1: resume})
    resp = resume_client.get("/api/v1/resumes/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["parsed_content"]["personal"]["name"] == "张三"
