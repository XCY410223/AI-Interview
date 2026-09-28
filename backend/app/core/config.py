"""统一配置：从环境变量加载（.env 不入库），禁止在代码中硬编码密钥（规范 §11.1）。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    APP_NAME: str = "ai-interview"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    # CORS：开发环境前端源（M1 计划 §7）
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 数据库
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5434
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ai_interview"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6382
    REDIS_DB: int = 0

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6382/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6382/2"

    # 对象存储（S3 协议）
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "ai-interview"
    S3_REGION: str = "us-east-1"

    # LLM 统一客户端
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_PRIMARY_MODEL: str = "deepseek-chat"
    LLM_FALLBACK_MODEL: str = "deepseek-reasoner"
    LLM_CONNECT_TIMEOUT: int = 5
    LLM_READ_TIMEOUT: int = 60
    LLM_TOTAL_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 3

    # Embedding（bge-m3，评估与生产同源，M4 计划 §四 PR-R3）
    EMBEDDING_MODEL: str = "bge-m3"
    # OpenAI 兼容 embeddings 端点（自部署 Xinference/TEI 或兼容网关）；涉密钥，交人工配 .env
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIM: int = 1024   # bge-m3 维度，入库/检索做维度断言（§十二）
    EMBEDDING_BATCH_SIZE: int = 32  # 入库批大小（§9.6）

    # 限流
    AI_RATE_LIMIT_PER_HOUR: int = 20
    MAX_QUESTIONS_PER_INTERVIEW: int = 15

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
