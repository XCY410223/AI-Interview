"""测试用内存 fakes（不依赖真实 Redis / PostgreSQL / MinIO，规范 §12）。"""
from __future__ import annotations

from types import SimpleNamespace


class FakeRedis:
    """dict-backed async redis，覆盖限流（zset）与黑名单（get/set）。"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}

    async def zremrangebyscore(self, key: str, min_: float, max_: float) -> int:
        z = self._zsets.setdefault(key, {})
        to_del = [m for m, s in z.items() if min_ <= s <= max_]
        for m in to_del:
            del z[m]
        return len(to_del)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        self._zsets.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def zcard(self, key: str) -> int:
        return len(self._zsets.get(key, {}))

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._data[key] = value
        return True

    async def aclose(self) -> None:
        pass


class FakeResult:
    def __init__(self, scalar_one_or_none=None, scalar_one=None, scalars: list | None = None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar_one = scalar_one
        self._scalars = scalars

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar_one(self):
        return self._scalar_one

    def scalars(self):
        return _FakeScalars(self._scalars or [])

    def all(self):
        return self._scalars or []


class _FakeScalars:
    def __init__(self, items: list):
        self._items = items

    def all(self) -> list:
        return self._items


class FakeSession:
    """内存 async session：add/flush 分配 id，execute/get 返回预置结果。"""

    def __init__(self) -> None:
        self._counter = 0
        self.added: list = []
        self.committed = False
        self._execute_result = FakeResult()
        self._get_map: dict[int, object] = {}

    def configure(
        self,
        *,
        scalar_one_or_none=None,
        scalar_one=None,
        scalars: list | None = None,
        get_map: dict | None = None,
    ) -> "FakeSession":
        self._execute_result = FakeResult(scalar_one_or_none, scalar_one, scalars)
        if get_map is not None:
            self._get_map = get_map
        return self

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _assign_ids(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id()

    def add(self, obj) -> None:  # SQLAlchemy 的 add 是同步方法（不 await）
        self.added.append(obj)

    async def flush(self) -> None:
        self._assign_ids()

    async def commit(self) -> None:
        self._assign_ids()  # SQLAlchemy commit 前会自动 flush（分配 id）
        self.committed = True

    async def refresh(self, obj) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def get(self, model, pk: int):
        return self._get_map.get(pk)

    async def execute(self, stmt):
        return self._execute_result

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args) -> bool:
        return False


class FakeStorage:
    """内存对象存储：dict 存 object_key -> bytes。"""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = objects or {}

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def get_object(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    async def ensure_bucket(self) -> None:
        pass


def make_user(*, user_id: int = 1, email: str = "a@b.com", password_hash: str = "h", is_active: bool = True):
    return SimpleNamespace(
        id=user_id, email=email, password_hash=password_hash, is_active=is_active,
        avatar_url=None, last_login_at=None, deleted_at=None, created_at=None,
    )


def make_resume(
    *,
    resume_id: int = 1,
    user_id: int = 1,
    object_key: str = "resumes/1_abc.pdf",
    status: str = "pending",
    original_ext: str = "pdf",
    retry_count: int = 0,
):
    return SimpleNamespace(
        id=resume_id, user_id=user_id, object_key=object_key, original_ext=original_ext,
        size_bytes=100, mime_type="application/pdf", status=status,
        parsed_content=None, error_message=None, retry_count=retry_count,
        uploaded_at=None, processed_at=None, deleted_at=None,
    )
