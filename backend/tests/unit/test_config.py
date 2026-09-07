"""config 单测：Settings 默认值、database_url 拼装、get_settings 缓存。"""
from app.core.config import Settings, get_settings, settings


def test_defaults():
    assert settings.APP_NAME == "ai-interview"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.POSTGRES_PORT == 5434
    assert settings.REDIS_PORT == 6382


def test_database_url_uses_asyncpg():
    url = settings.database_url
    assert url.startswith("postgresql+asyncpg://")
    assert f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}" in url
    assert f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}" in url
    assert url.endswith(f"/{settings.POSTGRES_DB}")


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
    assert get_settings() is settings


def test_settings_accepts_overrides():
    s = Settings(SECRET_KEY="x", POSTGRES_PORT=9999)
    assert s.SECRET_KEY == "x"
    assert s.POSTGRES_PORT == 9999
