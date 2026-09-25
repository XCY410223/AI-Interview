"""邮件服务（M4 PR-R7-d）：SMTP/Brevo 发送，模板集中管理。

MVP：发送为 best-effort（记录日志）。SMTP 接入与 Brevo API key 属密钥/人工配置项
（§八交人工），此处仅留发送接口，避免在 HTTP 请求内同步阻塞。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send_confirmation(email: str) -> None:
        """发送 Waiting List 确认信（best-effort，SMTP 配置交人工后接入）。"""
        subject = "AI 面试平台 · 已加入等候名单"
        body = f"感谢订阅 {email}，产品内测开放时我们会第一时间通知你。"
        logger.info("waiting list confirmation email (mock) to=%s subject=%s body=%s", email, subject, body)
        # TODO(smtp): 接入 Brevo/SMTP 后在此真实发送（密钥走 .env，红线 2）

    @staticmethod
    def send(to: str, subject: str, body: str) -> None:
        logger.info("email (mock) to=%s subject=%s", to, subject)


__all__ = ["EmailService"]
