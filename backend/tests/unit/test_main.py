"""main 单测：应用工厂的 title、docs/openapi 路径、路由前缀。"""
from fastapi import FastAPI

from app.core.config import settings
from app.main import create_app


def test_create_app_returns_fastapi():
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == settings.APP_NAME
    assert app.version == "0.1.0"


def test_docs_urls():
    app = create_app()
    assert app.docs_url == "/api/docs"
    assert app.openapi_url == "/api/openapi.json"


def test_routes_prefixed_with_api_v1():
    app = create_app()
    paths = app.openapi()["paths"]
    assert "/api/v1/health" in paths
