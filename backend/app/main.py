"""应用入口：仅负责组装（规范 §3.2/§4）。

- 全局异常处理器：AppError → {code, message, data:null}（§6.3）；
- request_id 中间件：生成/透传 trace_id（§13）；
- CORS：开发环境允许 localhost:5173（M1 计划 §7）。
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router_registry import api_router
from app.common.exceptions import AppError
from app.core.config import settings
from app.core.log_config import request_id_var, setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # 启动：初始化连接池、Redis 等（禁止在此处同步调用 LLM）
    yield
    # 关闭：释放资源


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # CORS（开发：localhost:5173）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # request_id 中间件（§13）
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    # 统一异常响应（§6.3）：业务异常 → {code, message, data:null}
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "服务内部错误", "data": None},
        )

    # 唯一对外 API 层：/api/v1
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
