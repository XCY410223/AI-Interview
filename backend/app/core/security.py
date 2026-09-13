"""安全工具：密码哈希（bcrypt cost=12）与 JWT 签发/校验（规范 §11.1/§11.2）。

- 密码只存 bcrypt 哈希，绝不存明文（红线：敏感信息不入库）。
- access token：30min；refresh token：7d，带 jti 供轮换/黑名单（§11.2）。
- refresh token 的 jti 通过 sha256(jti + SECRET_KEY) 生成 DB 存根 hash，不存原文。
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_COST = 12
BCRYPT_COST_TEST = 4  # 测试环境用低 cost 加速（规范 §12 与 M1 计划 §3.4）
JWT_ALGORITHM = "HS256"


def hash_password(password: str, *, cost: int = BCRYPT_COST) -> str:
    """生成 bcrypt 哈希（默认 cost=12）。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=cost)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配；哈希格式非法时返回 False（不抛异常）。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int) -> str:
    """签发 access token（sub=user_id，type=access，默认 30min）。"""
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """签发 refresh token，返回 (token, jti)。jti 用于轮换与黑名单。"""
    jti = uuid.uuid4().hex
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM), jti


def decode_token(token: str, expected_type: str | None = None) -> dict:
    """解码并校验 JWT；失败抛 jwt.PyJWTError（ExpiredSignatureError / InvalidTokenError）。"""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    if expected_type is not None and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"token type 不匹配，期望 {expected_type}")
    return payload


def hash_refresh_token(jti: str) -> str:
    """refresh token 的 DB 存根 hash：sha256(jti + SECRET_KEY)，不存原文。"""
    return hashlib.sha256(f"{jti}{settings.SECRET_KEY}".encode("utf-8")).hexdigest()
