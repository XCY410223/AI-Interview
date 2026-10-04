"""refresh token 轮换 + Redis 黑名单（规范 §11.2 / M1 计划 §3.4）。

- 每次 /refresh 成功后：旧 refresh 翻 revoked，replaced_by 指向新 token；
- 收到已 revoked 的 refresh → 视为重放攻击 → 撤销整条链（防御 refresh 泄露）；
- 登出把 jti 写 Redis 黑名单（SETEX ttl=7d），即时失效。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AuthInvalidCredentials, AuthTokenExpired, AuthTokenRevoked
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from app.models.token import RefreshToken

_REFRESH_BLACKLIST_TTL_SECONDS = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


class TokenService:
    @staticmethod
    async def issue(db: AsyncSession, user_id: int) -> dict:
        """签发 access + refresh 双 token（refresh 落库；由调用方 commit）。"""
        access_token = create_access_token(user_id)
        refresh_token, jti = create_refresh_token(user_id)
        record = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(jti),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(record)
        await db.flush()
        return {"access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    async def _lookup(db: AsyncSession, token_hash: str) -> RefreshToken | None:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        return result.scalar_one_or_none()

    @staticmethod
    async def _revoke_chain(db: AsyncSession, record: RefreshToken) -> None:
        """沿 replaced_by 方向撤销该 record 及其全部后代（整链撤销，§3.4）。"""
        seen: set[int] = set()
        current: RefreshToken | None = record
        while current is not None and current.id not in seen:
            seen.add(current.id)
            current.revoked = True
            next_id = current.replaced_by
            current = await db.get(RefreshToken, next_id) if next_id is not None else None
        await db.commit()

    @staticmethod
    async def rotate(db: AsyncSession, redis: Redis | None, refresh_token: str) -> dict:
        """校验并轮换 refresh token，返回新的双 token。"""
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.ExpiredSignatureError:
            raise AuthTokenExpired()
        except pyjwt.PyJWTError:
            raise AuthInvalidCredentials()

        jti = payload.get("jti") or ""
        token_hash = hash_refresh_token(jti)
        record = await TokenService._lookup(db, token_hash)

        # Redis 黑名单优先（登出即时失效）
        if redis is not None and jti:
            if await redis.get(f"blacklist:{jti}") is not None:
                if record is not None:
                    await TokenService._revoke_chain(db, record)
                raise AuthTokenRevoked()

        if record is None:
            raise AuthInvalidCredentials()
        if record.revoked:
            # 重放攻击 → 整链撤销（§3.4 关键）
            await TokenService._revoke_chain(db, record)
            raise AuthTokenRevoked()
        if record.expires_at is not None and record.expires_at < datetime.now(timezone.utc):
            raise AuthTokenExpired()

        user_id = int(payload["sub"])
        # 旧 token 失效 + 指向新 token
        record.revoked = True
        record.last_used_at = datetime.now(timezone.utc)
        access_token = create_access_token(user_id)
        new_refresh, new_jti = create_refresh_token(user_id)
        new_record = RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(new_jti),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_record)
        await db.flush()
        record.replaced_by = new_record.id
        await db.commit()
        return {"access_token": access_token, "refresh_token": new_refresh}

    @staticmethod
    async def revoke(db: AsyncSession, redis: Redis | None, refresh_token: str) -> None:
        """登出：DB 置 revoked + Redis 黑名单（幂等，无效 token 静默成功）。"""
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except pyjwt.PyJWTError:
            return
        jti = payload.get("jti") or ""
        token_hash = hash_refresh_token(jti)
        record = await TokenService._lookup(db, token_hash)
        if record is not None and not record.revoked:
            record.revoked = True
            await db.commit()
        if redis is not None and jti:
            await redis.set(f"blacklist:{jti}", "1", ex=_REFRESH_BLACKLIST_TTL_SECONDS)

    @staticmethod
    async def revoke_all_for_user(db: AsyncSession, user_id: int) -> int:
        """撤销指定用户名下全部未撤销的 refresh token（重置密码「全下线」语义，§3.5）。"""
        result = await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        # DML 结果上的 rowcount 位于 CursorResult（asyncpg 可能返回 None），此处 getattr 兜底
        return int(getattr(result, "rowcount", 0) or 0)
