"""应用入口：仅负责组装，不承载业务逻辑（规范 §3.2/§4）。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router_registry import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    # 唯一对外 API 层：/api/v1
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
