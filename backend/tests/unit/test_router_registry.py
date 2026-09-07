"""router_registry 单测：路由已注册、无重复 path+method（红线 1 自动化校验）。"""
from collections import Counter

from fastapi import FastAPI

from app.api.v1.router_registry import api_router


def _openapi_paths() -> dict:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    return app.openapi()["paths"]


def test_health_route_registered():
    paths = _openapi_paths()
    assert "/api/v1/health" in paths


def test_no_duplicate_routes():
    paths = _openapi_paths()
    methods = [(path, method) for path, ops in paths.items() for method in ops]
    dupes = [k for k, c in Counter(methods).items() if c > 1]
    assert not dupes, f"发现重复路由: {dupes}"
