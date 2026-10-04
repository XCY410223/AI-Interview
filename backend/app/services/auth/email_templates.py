"""忘记密码找回邮件模板（§3.6）：模板集中管理（类比红线 9「Prompt 集中管理」）。

邮件正文含一次性 token 链接，仅存在于邮件内容中；调用方与任务日志均禁止打印。
"""
from __future__ import annotations

from app.core.config import settings

PASSWORD_RESET_SUBJECT = "AI 面试平台 · 重置密码"


def build_password_reset_email(token: str) -> tuple[str, str]:
    """构造重置邮件 (subject, body)，含 ${FRONTEND_BASE_URL}/reset-password?token=... 链接。"""
    link = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
    ttl = settings.PASSWORD_RESET_TOKEN_TTL_MINUTES
    body = (
        "我们收到了你重置密码的请求。\n\n"
        f"请点击以下链接重置密码（{ttl} 分钟内有效）：\n"
        f"{link}\n\n"
        "如果这不是你的操作，请忽略本邮件，你的密码不会被更改。"
    )
    return PASSWORD_RESET_SUBJECT, body


__all__ = ["PASSWORD_RESET_SUBJECT", "build_password_reset_email"]
