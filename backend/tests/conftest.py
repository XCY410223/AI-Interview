"""pytest 全局配置：确保 backend/ 在 sys.path，并提供 API 集成测试用 client。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.main import app
from tests.fakes import FakeRedis, FakeSession


@pytest.fixture
def client():
    """TestClient + 依赖覆盖（get_db / get_redis 走内存 fakes，不触真实 DB/Redis）。"""
    state = {"db": FakeSession(), "redis": FakeRedis()}

    async def get_db_override():
        yield state["db"]

    async def get_redis_override():
        yield state["redis"]

    app.dependency_overrides[deps.get_db] = get_db_override
    app.dependency_overrides[deps.get_redis] = get_redis_override
    with TestClient(app) as c:
        c.state = state
        yield c
    app.dependency_overrides.clear()
