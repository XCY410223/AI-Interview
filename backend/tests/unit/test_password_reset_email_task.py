"""忘记密码找回邮件任务单测（§5）：发送 / 用户不存在跳过 / SMTP 失败重试。"""
from __future__ import annotations

import asyncio

import pytest

from app.tasks.email import _run
from tests.fakes import FakeSession, make_user


def run(coro):
    return asyncio.run(coro)


def _factory(get_map):
    return lambda: FakeSession().configure(get_map=get_map)


def test_run_sends_email_to_looked_up_user():
    user = make_user(user_id=1, email="a@b.com")
    sent: list[tuple[str, str, str]] = []

    def fake_send(to, subject, body):
        sent.append((to, subject, body))

    result = run(_run(1, token="tok", session_factory=_factory({1: user}), send=fake_send))
    assert result == {"status": "sent", "user_id": 1}
    assert sent[0][0] == "a@b.com"  # 收件人来自 worker 内自查，非入参明文
    assert "token=tok" in sent[0][2]  # 正文含一次性链接


def test_run_skips_when_user_not_found():
    sent: list = []
    result = run(_run(1, token="tok", session_factory=_factory({}), send=lambda *a: sent.append(a)))
    assert result == {"status": "not_found", "user_id": 1}
    assert sent == []


def test_run_raises_when_send_fails_without_task():
    def boom(to, subject, body):
        raise RuntimeError("smtp down")

    with pytest.raises(RuntimeError):
        run(_run(1, token="tok", session_factory=_factory({1: make_user()}), send=boom))


def test_run_retries_when_send_fails_with_task():
    class FakeTask:
        def __init__(self):
            self.retried = None

        def retry(self, exc=None):
            self.retried = exc
            raise RuntimeError("celery retry")

    task = FakeTask()

    def boom(to, subject, body):
        raise RuntimeError("smtp down")

    with pytest.raises(RuntimeError):
        run(_run(1, token="tok", task=task, session_factory=_factory({1: make_user()}), send=boom))
    assert isinstance(task.retried, RuntimeError)  # 触发重试
