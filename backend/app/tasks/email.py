"""邮件发送 Celery 任务（M4 PR-R7-d）：Waiting List 确认信。

发送失败不应影响订阅主流程（best-effort），因此不重试、不阻塞。
"""
from __future__ import annotations

import logging

from celery import shared_task

from app.services.common.email import EmailService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="email.send_waiting_list_confirmation", max_retries=0)
def send_waiting_list_confirmation(self, email: str) -> dict:
    try:
        EmailService.send_confirmation(email)
    except Exception as exc:  # best-effort：邮件失败不影响订阅
        logger.warning("waiting list confirmation email failed email=%s: %s", email, exc)
    return {"status": "sent", "email": email}


__all__ = ["send_waiting_list_confirmation"]
