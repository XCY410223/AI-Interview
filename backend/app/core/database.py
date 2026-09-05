"""数据库引擎与 session 工厂（SQLAlchemy 2.0 async，规范 §5/§6.4）。

session 统一通过 FastAPI `Depends` 提供，Service 层禁止自行 new session。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI 依赖：请求级 session，用完自动关闭。"""
    async with async_session_factory() as session:
        yield session
