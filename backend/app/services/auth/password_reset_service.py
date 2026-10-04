"""忘记密码找回服务（§3.5）：邮件链接一次性 token，状态全部存 Redis（零 DB 迁移）。

安全语义（逐条对应设计 §2.1）：
- 防枚举：无论邮箱是否注册一律返回 200 + 相同文案；不存在邮箱也跑一次 dummy bcrypt 抹平时差。
- 单次有效：Redis GETDEL 原子取删，同一 token 二次使用直接失败（防重放）。
- 重置即全下线：改密成功后撤销该 user_id 名下全部 refresh token。
- 限流：IP 级 + 邮箱级滑动窗口，均无条件计数（避免「存在的邮箱第 4 次 429、不存在的永不 429」
  的限流侧信道泄漏邮箱存在性）。
"""
from __future__ import annotations

import hashlib
import logging

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AuthRateLimited, AuthResetTokenInvalid
from app.core.config import settings
from app.core.rate_limit import window_record
from app.core.security import generate_reset_token, hash_password, hash_reset_token
from app.models.user import User
from app.services.auth.token_service import TokenService

logger = logging.getLogger(__name__)

WINDOW_HOUR = 3600


class PasswordResetService:
    RESET_KEY = "pwd_reset:{token_hash}"

    @staticmethod
    async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _email_key(email: str) -> str:
        return f"forgot:email:{hashlib.sha256(email.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _enqueue(user_id: int, token: str) -> str:
        """下发重置邮件任务（延迟导入避免循环依赖）。"""
        from app.tasks.email import send_password_reset_email

        result = send_password_reset_email.delay(user_id=user_id, token=token)
        return str(getattr(result, "id", "") or "")

    @staticmethod
    async def request_reset(db: AsyncSession, redis: Redis, *, email: str, ip: str) -> None:
        """限流 → 查用户 → 存 token → 投递邮件。不存在用户静默返回（防枚举）。"""
        ip_key = f"forgot:ip:{ip}"
        if await window_record(redis, ip_key, WINDOW_HOUR) > settings.PASSWORD_RESET_IP_LIMIT_PER_HOUR:
            raise AuthRateLimited()

        email_key = PasswordResetService._email_key(email)
        if await window_record(redis, email_key, WINDOW_HOUR) > settings.PASSWORD_RESET_EMAIL_LIMIT_PER_HOUR:
            raise AuthRateLimited()

        user = await PasswordResetService._get_user_by_email(db, email)
        if user is None:
            # 耗时侧信道抹平：不存在的邮箱也执行一次同 cost 的 bcrypt（§2.1）
            hash_password("password-reset-timing-dummy")
            return

        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        await redis.set(
            PasswordResetService.RESET_KEY.format(token_hash=token_hash),
            str(user.id),
            ex=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES * 60,
        )
        try:
            PasswordResetService._enqueue(user.id, token)
        except Exception:  # 邮件投递失败不影响重置请求（best-effort）
            logger.warning("password reset email enqueue failed user_id=%s", user.id)
        logger.info("auth.password_reset_request user_id=%s", user.id)

    @staticmethod
    async def validate(redis: Redis, token: str) -> bool:
        """校验 token 是否仍有效（只读，不消费）。"""
        key = PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))
        return await redis.get(key) is not None

    @staticmethod
    async def reset_password(db: AsyncSession, redis: Redis, *, token: str, new_password: str) -> None:
        """GETDEL 原子取删 → 改密 → 撤销该用户全部 refresh token → 单事务 commit。"""
        key = PasswordResetService.RESET_KEY.format(token_hash=hash_reset_token(token))
        raw = await redis.getdel(key)
        if raw is None:
            raise AuthResetTokenInvalid()

        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            raise AuthResetTokenInvalid()

        user = await db.get(User, user_id)
        if user is None or getattr(user, "deleted_at", None) is not None:
            raise AuthResetTokenInvalid()

        user.password_hash = hash_password(new_password)
        await TokenService.revoke_all_for_user(db, user_id)
        await db.commit()
        logger.info("auth.password_reset user_id=%s", user_id)


__all__ = ["PasswordResetService", "WINDOW_HOUR"]
