"""真题检索（M4 PR-R5）：pgvector cosine top-K + Redis 缓存（spec §9.6）。

- 检索域：同 company+position+difficulty 的 chunk 行（embedding 非空）；
- 缓存 key `qbank:search:{company}:{position}:{difficulty}`，TTL 10min；
- 检索零命中 → 返回空列表（调用方静默回退普通出题，不报错）。
"""
from __future__ import annotations

import json

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import QuestionBankRetrievalError
from app.core.llm.client import LLMError, llm_client
from app.models.question import QuestionBankItem
from app.schemas.question_bank import QuestionBankSearchItem

SEARCH_CACHE_TTL = 600  # 10min（spec §9.6）
DEFAULT_TOP_K = 8


def cache_key(company: str, position: str, difficulty: str) -> str:
    return f"qbank:search:{company}:{position}:{difficulty}"


def build_query_text(company: str, position: str, difficulty: str) -> str:
    """检索查询文本（embedding 输入），与缓存 key 字段一致。"""
    return f"{company} {position} {difficulty} 面试真题"


async def cosine_search(
    db: AsyncSession,
    *,
    query_vector: list[float],
    company: str,
    position: str,
    difficulty: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[QuestionBankItem]:
    """pgvector cosine 相似度 top-K（距离升序 = 相似度降序）。"""
    stmt = (
        select(QuestionBankItem)
        .where(
            QuestionBankItem.company == company,
            QuestionBankItem.position == position,
            QuestionBankItem.difficulty == difficulty,
            QuestionBankItem.embedding.is_not(None),
            QuestionBankItem.deleted_at.is_(None),
        )
        .order_by(QuestionBankItem.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def _cache_get(redis: Redis, key: str) -> list[QuestionBankSearchItem] | None:
    raw = await redis.get(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    return [QuestionBankSearchItem.model_validate(d) for d in data if isinstance(d, dict)]


async def _cache_set(redis: Redis, key: str, items: list[QuestionBankSearchItem]) -> None:
    await redis.set(
        key,
        json.dumps([i.model_dump() for i in items], ensure_ascii=False),
        ex=SEARCH_CACHE_TTL,
    )


def _to_search_items(rows: list[QuestionBankItem]) -> list[QuestionBankSearchItem]:
    return [
        QuestionBankSearchItem(
            id=r.id,
            company=r.company,
            position=r.position,
            difficulty=r.difficulty,
            content=r.content,
            source_url=r.source_url,
        )
        for r in rows
    ]


async def search(
    db: AsyncSession,
    *,
    company: str,
    position: str,
    difficulty: str,
    top_k: int = DEFAULT_TOP_K,
    redis: Redis | None = None,
    embed_fn=None,
) -> list[QuestionBankSearchItem]:
    """检索真题：先查缓存 → miss 则 embed 查询向量 → cosine top-K → 回填缓存。"""
    embed_fn = embed_fn or llm_client.embed_texts
    key = cache_key(company, position, difficulty)

    if redis is not None:
        cached = await _cache_get(redis, key)
        if cached is not None:
            return cached[:top_k]

    try:
        vectors = await embed_fn([build_query_text(company, position, difficulty)])
    except LLMError as exc:
        # embedding 未配置/调用失败 → 明确报错而非落入通用 500（§9.6 依赖 EMBEDDING_*）
        raise QuestionBankRetrievalError() from exc
    query_vector = vectors[0]
    rows = await cosine_search(
        db,
        query_vector=query_vector,
        company=company,
        position=position,
        difficulty=difficulty,
        top_k=top_k,
    )
    items = _to_search_items(rows)

    # 仅缓存非空结果：入库是异步的，缓存空结果会让「入库后立刻检索」吃到 10min 陈旧空缓存
    if redis is not None and items:
        await _cache_set(redis, key, items)
    return items


__all__ = [
    "SEARCH_CACHE_TTL",
    "DEFAULT_TOP_K",
    "cache_key",
    "build_query_text",
    "cosine_search",
    "search",
]
