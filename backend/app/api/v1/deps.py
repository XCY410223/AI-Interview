"""依赖注入：数据库 session、当前用户、Redis 等（规范 §6.4）。

红线：Service 层禁止自行 new session；统一通过 FastAPI Depends 提供。
"""
from app.core.database import get_db  # noqa: F401  # 复用统一 session 依赖

# 待实现（按需解锁）：
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# async def get_current_user(...) -> User: ...
# async def get_redis(...) -> Redis: ...
