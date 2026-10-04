"""面经入库 Celery 任务：切片→去重→embedding→入库（M4 计划 §四 PR-R4，spec §9.6 逐条）。

- 入参只传 item_id（§10.2）；worker 内独立 session，事务边界在任务内；
- 幂等可重跑：作业行 status=completed 短路；chunk 行 content_hash UNIQUE 去重（同 item_id
  重复投递不产生重复行）；
- embedding 走统一客户端（红线 6），批大小 ≤ settings.EMBEDDING_BATCH_SIZE；
- 去重仅同 company+position 域（M4 决策 D5），cosine > 0.92 丢弃。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from app.core.database import async_session_factory, celery_session_factory
from app.core.llm.client import llm_client
from app.models.question import (
    QUESTION_BANK_STATUS_COMPLETED,
    QUESTION_BANK_STATUS_FAILED,
    QUESTION_BANK_STATUS_PENDING,
    QUESTION_BANK_STATUS_PROCESSING,
    QuestionBankItem,
)
from app.services.question_bank.ingest import (
    assert_embedding_dim,
    batch_chunks,
    content_hash,
    should_drop,
    slice_text,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


@shared_task(
    bind=True,
    name="rag.ingest",
    max_retries=MAX_RETRIES,
    default_retry_delay=15,
    retry_backoff=True,
    retry_jitter=True,
    time_limit=300,
    soft_time_limit=270,
)
def ingest_item_task(self, item_id: int) -> dict:
    """Celery 入口：入参只接 item_id（§10.2）。"""
    return asyncio.run(_run_ingest(item_id, task=self, session_factory=celery_session_factory))


async def _load_existing(session_factory, company: str, position: str) -> list[QuestionBankItem]:
    """同 company+position 的既有 chunk 行（带 embedding），用于 hash 去重 + cosine 去重。"""
    async with session_factory() as db:
        stmt = (
            select(QuestionBankItem)
            .where(
                QuestionBankItem.company == company,
                QuestionBankItem.position == position,
                QuestionBankItem.embedding.is_not(None),
                QuestionBankItem.deleted_at.is_(None),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)


async def _run_ingest(
    item_id: int,
    *,
    task=None,
    session_factory=async_session_factory,
    embed_fn=None,
) -> dict:
    """入库管线主体（独立函数便于注入 fake 单测）。"""
    embed_fn = embed_fn or llm_client.embed_texts

    # 1. 读作业 + 幂等短路 + 置 processing（独立 session）
    async with session_factory() as db:
        item = await db.get(QuestionBankItem, item_id)
        if item is None:
            return {"status": "not_found", "item_id": item_id}
        if item.status == QUESTION_BANK_STATUS_COMPLETED:
            return {"status": "skipped", "item_id": item_id}
        company = item.company
        position = item.position
        user_id = item.user_id
        difficulty = item.difficulty
        source_url = item.source_url
        raw_content = item.content
        item.status = QUESTION_BANK_STATUS_PROCESSING
        await db.commit()

    try:
        # 2. 切片（§9.6：300~500 字）
        chunks = slice_text(raw_content)
        existing = await _load_existing(session_factory, company, position)
        existing_hashes = {e.content_hash for e in existing}
        existing_vectors = [e.embedding for e in existing if e.embedding]

        # 3. hash 去重 + 批量 embedding（≤32/批，统一客户端）
        new_chunks = [c for c in chunks if content_hash(company, position, c) not in existing_hashes]
        vectors: list[list[float]] = []
        for batch in batch_chunks(new_chunks):
            for vec in await embed_fn(batch):
                assert_embedding_dim(vec)
                vectors.append(vec)

        # 4. cosine 去重 + 逐 chunk 落行
        inserted = 0
        deduped = 0
        async with session_factory() as db:
            for chunk, vec in zip(new_chunks, vectors):
                if should_drop(existing_vectors, vec):
                    logger.info("chunk 去重丢弃 company=%s position=%s", company, position)
                    deduped += 1
                    continue
                db.add(
                    QuestionBankItem(
                        user_id=user_id,
                        company=company,
                        position=position,
                        difficulty=difficulty,
                        content=chunk,
                        source_url=source_url,
                        collected_at=datetime.now(timezone.utc),
                        content_hash=content_hash(company, position, chunk),
                        embedding=vec,
                        status=QUESTION_BANK_STATUS_COMPLETED,
                    )
                )
                existing_vectors.append(vec)  # 同批内也去重
                inserted += 1
            await db.commit()
    except Exception as exc:
        exhausted = await _handle_retry(session_factory, item_id, exc)
        if exhausted:
            return {"status": "failed", "item_id": item_id, "error": str(exc)}
        if task is not None:
            raise task.retry(exc=exc)
        raise exc

    # 5. 回写作业 completed
    async with session_factory() as db:
        item = await db.get(QuestionBankItem, item_id)
        if item is not None:
            item.status = QUESTION_BANK_STATUS_COMPLETED
            item.error_message = None
            await db.commit()

    logger.info(
        "rag ingest completed item_id=%s chunks=%s inserted=%s deduped=%s",
        item_id, len(chunks), inserted, deduped,
    )
    return {
        "status": "completed",
        "item_id": item_id,
        "chunks_total": len(chunks),
        "chunks_inserted": inserted,
        "chunks_deduped": deduped,
    }


async def _handle_retry(session_factory, item_id: int, exc: Exception) -> bool:
    """瞬时错误：retry_count+1；耗尽 → failed（返回 True），否则回 pending（返回 False）。"""
    async with session_factory() as db:
        item = await db.get(QuestionBankItem, item_id)
        if item is None:
            return True
        item.retry_count += 1
        if item.retry_count > MAX_RETRIES:
            item.status = QUESTION_BANK_STATUS_FAILED
            item.error_message = str(exc)
            await db.commit()
            return True
        item.status = QUESTION_BANK_STATUS_PENDING
        await db.commit()
        return False


__all__ = ["ingest_item_task", "_run_ingest"]
