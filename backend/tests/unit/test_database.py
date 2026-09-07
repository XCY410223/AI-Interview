"""database 单测：asyncpg 引擎与 session 工厂。"""
import asyncio

from app.core.database import async_session_factory, engine, get_db


def test_engine_uses_asyncpg():
    assert "asyncpg" in str(engine.url)


def test_session_factory_exists():
    assert async_session_factory is not None


def test_get_db_yields_session():
    async def _collect():
        async for session in get_db():
            return session
        return None

    session = asyncio.run(_collect())
    assert session is not None
