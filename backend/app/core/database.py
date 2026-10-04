"""数据库引擎与 session 工厂（SQLAlchemy 2.0 async，规范 §5/§6.4）。

session 统一通过 FastAPI `Depends` 提供，Service 层禁止自行 new session。
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Celery 任务专用：每个任务走独立 asyncio.run（独立 event loop），
# 复用进程级连接池会跨 loop 复用 asyncpg 连接（"attached to a different loop"），
# 故此处用 NullPool——每次新建连接、用完即关，跨 loop 安全（低并发任务无性能顾虑）。
celery_engine = create_async_engine(settings.database_url, poolclass=NullPool)
celery_session_factory = async_sessionmaker(celery_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：请求级 session，用完自动关闭。"""
    async with async_session_factory() as session:
        yield session
