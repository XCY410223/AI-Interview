"""账户模块 schema（注册/登录/Token，规范 §6.2 / M1 计划 §3.3）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="至少 8 位（§3.5 弱密码校验）")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserOut(ORMModel):
    id: int
    email: str
    avatar_url: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """register / login 成功响应（§3.3）。"""

    user: UserOut
    access_token: str
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128, description="重置 token（一次性）")
    new_password: str = Field(min_length=8, max_length=128, description="至少 8 位（与注册同规则）")


class ResetTokenValidateResponse(BaseModel):
    valid: bool


class AuthMessageResponse(BaseModel):
    """forgot-password / reset-password 统一成功响应（§3.2）。"""

    code: int = 0
    message: str
    data: Any = None
