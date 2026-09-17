"""测试用内存 fakes（不依赖真实 Redis / PostgreSQL / MinIO，规范 §12）。"""
from __future__ import annotations

from types import SimpleNamespace

from app.schemas.interview import QuestionItem


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

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

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


def _default_questions() -> list[dict]:
    return [
        {"question_index": 0, "round": 0, "category": "项目", "content": "介绍你最复杂的项目",
         "reference_points": ["技术选型", "难点"], "difficulty": "medium"},
        {"question_index": 1, "round": 0, "category": "知识", "content": "解释索引原理",
         "reference_points": ["B+树"], "difficulty": "medium"},
        {"question_index": 2, "round": 0, "category": "行为", "content": "如何处理冲突",
         "reference_points": ["沟通"], "difficulty": "medium"},
    ]


def make_interview(
    *,
    interview_id: int = 1,
    user_id: int = 1,
    resume_id: int | None = 1,
    position: str = "后端工程师",
    difficulty: str = "medium",
    question_count: int = 3,
    style: str = "friendly",
    status: str = "created",
    current_question_index: int = 0,
    current_round: int = 0,
    questions_json: list | None = None,
    config_json: dict | None = None,
):
    return SimpleNamespace(
        id=interview_id, user_id=user_id, resume_id=resume_id, position=position,
        difficulty=difficulty, question_count=question_count, style=style, status=status,
        current_question_index=current_question_index, current_round=current_round,
        questions_json=questions_json if questions_json is not None else _default_questions(),
        config_json=config_json, completed_at=None,
        deleted_at=None, created_at=None, updated_at=None,
    )


def make_interview_message(
    *,
    message_id: int = 1,
    interview_id: int = 1,
    question_index: int = 0,
    round_: int = 0,
    role: str = "candidate",
    content: str = "回答",
    event_type: str = "answer",
    payload_json: dict | None = None,
):
    return SimpleNamespace(
        id=message_id, interview_id=interview_id, question_index=question_index, round=round_,
        role=role, content=content, event_type=event_type, payload_json=payload_json,
        created_at=None, updated_at=None, deleted_at=None,
    )


def _to_question_items(raw: list) -> list:
    return [q if isinstance(q, QuestionItem) else QuestionItem.model_validate(q) for q in raw]


class FakeAIService:
    """测试用 AI 服务：可编程出题/评语/评分/追问结果，记录调用参数。"""

    def __init__(
        self,
        questions: list | None = None,
        feedback_chunks: list | None = None,
        score=None,
        followup=None,
    ):
        self.questions = _to_question_items(questions or _default_questions())
        self.feedback_chunks = feedback_chunks if feedback_chunks is not None else ["不错，", "有亮点。"]
        self.score = score if score is not None else SimpleNamespace(
            score=7.5, dimensions={"completeness": 8.0}, feedback="整体不错"
        )
        self.followup = followup if followup is not None else SimpleNamespace(
            need_follow_up=False, follow_up_hint="", reason="回答完整"
        )
        self.generate_calls: list[dict] = []
        self.stream_calls: list[dict] = []
        self.score_calls: list[dict] = []
        self.followup_calls: list[dict] = []

    async def generate_questions(self, **kw):
        self.generate_calls.append(kw)
        return self.questions

    async def stream_feedback(self, **kw):
        self.stream_calls.append(kw)
        for chunk in self.feedback_chunks:
            yield chunk

    async def evaluate_score(self, **kw):
        self.score_calls.append(kw)
        return self.score

    async def decide_follow_up(self, **kw):
        self.followup_calls.append(kw)
        return self.followup
