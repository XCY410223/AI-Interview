"""账户路由：注册/登录/刷新 token/登出/当前用户（M1 计划 §3.3）。

成功响应直接返回对象；错误由全局 ExceptionHandler 转为 {code, message, data:null}（§6.3）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.auth import (
    AuthMessageResponse,
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenValidateResponse,
    UserOut,
)
from app.services.auth.password_reset_service import PasswordResetService
from app.services.auth.service import AuthService
from app.services.auth.token_service import TokenService

router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user, tokens = await AuthService.register(
        db, redis, email=payload.email, password=payload.password, ip=_client_ip(request)
    )
    return {"user": UserOut.model_validate(user), **tokens}


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user, tokens = await AuthService.login(
        db, redis, email=payload.email, password=payload.password, ip=_client_ip(request)
    )
    return {"user": UserOut.model_validate(user), **tokens}


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await TokenService.rotate(db, redis, payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    await TokenService.revoke(db, redis, payload.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=dict)
async def me(current_user: User = Depends(get_current_user)):
    return {"user": UserOut.model_validate(current_user)}


@router.post("/forgot-password", response_model=AuthMessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """请求重置密码：无论邮箱是否注册一律返回相同文案（防枚举，§2.1）。"""
    await PasswordResetService.request_reset(db, redis, email=payload.email, ip=_client_ip(request))
    return AuthMessageResponse(message="如邮箱已注册，重置邮件已发送")


@router.get("/reset-password/validate", response_model=ResetTokenValidateResponse)
async def validate_reset_token(token: str, redis: Redis = Depends(get_redis)):
    """校验重置 token 是否有效（不区分过期/无效，防探测）。"""
    return ResetTokenValidateResponse(valid=await PasswordResetService.validate(redis, token))


@router.post("/reset-password", response_model=AuthMessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """使用一次性 token 重置密码；成功后该用户全部 refresh token 失效（全下线）。"""
    await PasswordResetService.reset_password(db, redis, token=payload.token, new_password=payload.new_password)
    return AuthMessageResponse(message="密码已重置，请重新登录")
