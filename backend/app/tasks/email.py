"""邮件发送 Celery 任务：密码找回重置邮件（可重试）。

- 密码找回邮件（§3.6）：慢 I/O 走 Celery（红线 4）；入参只传 user_id + token（不传邮箱明文），
  worker 内自查用户；SMTP 失败重试 3 次；日志只记 user_id，不打印 token / 邮箱正文。
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.core.database import async_session_factory
from app.models.user import User
from app.services.auth.email_templates import build_password_reset_email
from app.services.common.email import EmailService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="email.send_password_reset", max_retries=3, retry_backoff=True, default_retry_delay=15)
def send_password_reset_email(self, user_id: int, token: str) -> dict:
    """密码找回邮件任务：入参只接 user_id + token（worker 内自查邮箱，日志脱敏）。"""
    return asyncio.run(_run(user_id, token=token, task=self))


async def _run(user_id: int, *, token: str, task=None, session_factory=async_session_factory, send=None) -> dict:
    """任务主体（独立函数便于注入 fake 单测，类比 resume_parser._run）。"""
    async with session_factory() as db:
        user = await db.get(User, user_id)
    if user is None:
        logger.warning("password reset email skipped: user not found user_id=%s", user_id)
        return {"status": "not_found", "user_id": user_id}

    subject, body = build_password_reset_email(token)
    send = send or EmailService.send_password_reset
    try:
        send(user.email, subject, body)
    except Exception as exc:
        if task is not None:
            raise task.retry(exc=exc)
        raise exc
    logger.info("password reset email sent user_id=%s", user_id)
    return {"status": "sent", "user_id": user_id}


__all__ = ["send_password_reset_email", "_run"]
