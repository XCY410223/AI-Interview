"""账户服务：注册/登录（JWT 双 token）+ 双重限流（规范 §6.4 / M1 计划 §3.4）。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AuthEmailTaken, AuthInvalidCredentials, AuthRateLimited
from app.core.rate_limit import window_count, window_record
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.auth.token_service import TokenService

logger = logging.getLogger(__name__)


class AuthService:
    LOGIN_IP_LIMIT = 10       # 登录：同一 IP 10 次/分钟
    LOGIN_EMAIL_LIMIT = 5     # 登录：同一 email 5 次/分钟（失败计数）
    REGISTER_IP_LIMIT = 5     # 注册：同一 IP 5 次/小时
    WINDOW_MINUTE = 60
    WINDOW_HOUR = 3600

    @staticmethod
    async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def register(db: AsyncSession, redis: Redis, *, email: str, password: str, ip: str) -> tuple[User, dict]:
        ip_key = f"rate:register:ip:{ip}"
        if await window_record(redis, ip_key, AuthService.WINDOW_HOUR) > AuthService.REGISTER_IP_LIMIT:
            raise AuthRateLimited()

        if await AuthService._get_user_by_email(db, email) is not None:
            raise AuthEmailTaken()

        user = User(email=email, password_hash=hash_password(password), is_active=True)
        db.add(user)
        await db.flush()
        tokens = await TokenService.issue(db, user.id)
        await db.commit()
        await db.refresh(user)
        logger.info("auth.register user_id=%s", user.id)
        return user, tokens

    @staticmethod
    async def login(db: AsyncSession, redis: Redis, *, email: str, password: str, ip: str) -> tuple[User, dict]:
        ip_key = f"rate:login:ip:{ip}"
        if await window_record(redis, ip_key, AuthService.WINDOW_MINUTE) > AuthService.LOGIN_IP_LIMIT:
            raise AuthRateLimited()

        email_key = f"rate:login:email:{email}"
        if await window_count(redis, email_key, AuthService.WINDOW_MINUTE) >= AuthService.LOGIN_EMAIL_LIMIT:
            raise AuthRateLimited()

        user = await AuthService._get_user_by_email(db, email)
        # 认证失败统一返回 AUTH_INVALID_CREDENTIALS，不区分邮箱不存在 vs 密码错（§3.4）
        if user is None or not verify_password(password, user.password_hash):
            await window_record(redis, email_key, AuthService.WINDOW_MINUTE)
            raise AuthInvalidCredentials()
        if not user.is_active:
            raise AuthInvalidCredentials()

        user.last_login_at = datetime.now(timezone.utc)
        tokens = await TokenService.issue(db, user.id)
        await db.commit()
        await db.refresh(user)
        logger.info("auth.login user_id=%s", user.id)
        return user, tokens
