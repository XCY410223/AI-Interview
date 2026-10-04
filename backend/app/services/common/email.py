"""邮件服务（忘记密码找回）：SMTP 发送。

- 忘记密码找回（§3.6）：真实 smtplib 发送（零新依赖），SMTP_HOST 未配置时回退 mock；
  日志脱敏，禁止打印收件人 / 重置链接（含 token）/ 正文。
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send(to: str, subject: str, body: str) -> None:
        logger.info("email (mock) to=%s subject=%s", to, subject)

    @staticmethod
    def send_password_reset(to: str, subject: str, body: str) -> None:
        """发送重置密码邮件：SMTP 已配置走真实发送，否则 mock 回退（日志不打印收件人/正文）。"""
        if not settings.SMTP_HOST:
            logger.info("password reset email (mock, SMTP not configured) subject=%s", subject)
            return
        EmailService._send_via_smtp(to, subject, body)
        logger.info("password reset email sent subject=%s", subject)

    @staticmethod
    def _send_via_smtp(to: str, subject: str, body: str) -> None:
        """真实 SMTP 发送（同步 smtplib，Celery worker 同步上下文，零新依赖）。"""
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)


__all__ = ["EmailService"]
