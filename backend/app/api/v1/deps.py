"""依赖注入：数据库 session、当前用户、Redis（规范 §6.4）。

红线：Service 层禁止自行 new session；统一通过 FastAPI Depends 提供。
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import jwt as pyjwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AuthInvalidCredentials, AuthTokenExpired
from app.core.database import get_db
from app.core.redis import build_redis
from app.core.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = build_redis()
    try:
        yield redis
    finally:
        await redis.aclose()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 access token 并加载当前用户（软删/未激活 → 401，§3.5）。"""
    try:
        payload = decode_token(token, expected_type="access")
    except pyjwt.ExpiredSignatureError:
        raise AuthTokenExpired()
    except pyjwt.PyJWTError:
        raise AuthInvalidCredentials()

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise AuthInvalidCredentials()

    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise AuthInvalidCredentials()
    return user


__all__ = ["get_db", "get_redis", "get_current_user", "oauth2_scheme"]
