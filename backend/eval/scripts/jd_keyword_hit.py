"""JD 关键词命中率验收脚本（M4 计划 §四 PR-R2 / spec P1）。

逻辑：对每条 JD 黄金样本 → v2 出题 → 题目内容（含 reference_points）与能力项 keywords
匹配（分词 + 同义前缀），计算 `命中率 = 命中 must 级能力项数 / must 级能力项数`。
退出阈值 ≥ 0.8；脚本输出 JSON + 明细表，归档 `artifacts/`。

纯函数（keyword_match / evaluate_questions / aggregate）无 LLM 依赖，供单测；LLM 调用仅在
main() 内懒加载（真实跑分交人工，本地 CI 用 mock 断言纯函数）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# 判定阈值（spec P1）
HIT_RATE_THRESHOLD = 0.8

_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]+")
_CJK_PREFIX_MIN = 2


def keyword_match(text: str, keyword: str) -> bool:
    """关键词命中判定：大小写不敏感子串匹配 + 同义前缀（关键词为文本 token 前缀）。"""
    t = (text or "").lower()
    k = (keyword or "").strip().lower()
    if not k:
        return False
    if k in t:
        return True
    # 同义前缀：如「分布式」命中「分布式系统」「Kafka」命中「Kafka集群」
    for tok in _TOKEN_RE.findall(t):
        if len(k) >= _CJK_PREFIX_MIN and len(tok) >= len(k) and tok.startswith(k):
            return True
    return False


def evaluate_questions(questions: list[dict], capabilities: list[dict]) -> dict:
    """对一组题目与能力项计算命中明细（纯函数，questions 为 mock 出题结果）。"""
    must = [c for c in capabilities if (c or {}).get("importance") == "must"]
    if not must:
        return {"must_total": 0, "must_hit": 0, "hit_rate": None, "hits": [], "misses": []}

    text_parts: list[str] = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text_parts.append(str(q.get("content", "")))
        text_parts.append(" ".join(str(p) for p in (q.get("reference_points") or [])))
    corpus = " ".join(text_parts)

    hits: list[str] = []
    misses: list[str] = []
    for cap in must:
        name = str(cap.get("name", ""))
        keywords = cap.get("keywords") or []
        matched = any(keyword_match(corpus, kw) for kw in keywords)
        (hits if matched else misses).append(name)
    return {
        "must_total": len(must),
        "must_hit": len(hits),
        "hit_rate": len(hits) / len(must),
        "hits": hits,
        "misses": misses,
    }


def aggregate(per_sample: list[dict]) -> dict:
    """跨样本聚合命中率（命中总数 / must 总数）。"""
    total = sum(s["must_total"] for s in per_sample)
    hit = sum(s["must_hit"] for s in per_sample)
    return {
        "samples": len(per_sample),
        "must_total": total,
        "must_hit": hit,
        "hit_rate": (hit / total) if total else None,
    }


def load_samples(path: str | Path) -> list[dict]:
    """加载 JD 黄金样本（JSONL），忽略空行与非法行。"""
    samples: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return samples


def _generate_for_sample(sample: dict) -> list[dict]:
    """懒加载 AI 服务，按样本出题（真实 LLM 跑分，本地 CI 不调用）。"""
    import asyncio

    from app.schemas.question_bank import JDCapability
    from app.services.interview.ai_service import InterviewAIService

    async def _run() -> list[dict]:
        caps = [JDCapability.model_validate(c) for c in (sample.get("capabilities") or [])]
        questions = await InterviewAIService().generate_questions(
            position=sample.get("position", ""),
            difficulty=sample.get("difficulty", "medium"),
            resume_summary=sample.get("resume_summary", ""),
            question_count=sample.get("question_count", 8),
            capabilities=caps,
        )
        return [q.model_dump() for q in questions]

    return asyncio.run(_run())


def _write_artifacts(report: dict, artifacts_dir: Path) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / "jd_keyword_hit_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dataset = Path(argv[0]) if argv else Path("eval/datasets/golden_v1_jd.jsonl")
    artifacts_dir = Path(argv[1]) if len(argv) > 1 else Path("artifacts")

    samples = load_samples(dataset)
    per_sample: list[dict] = []
    for sample in samples:
        questions = _generate_for_sample(sample)
        result = evaluate_questions(questions, sample.get("capabilities", []))
        per_sample.append({**result, "position": sample.get("position", "")})

    report = {"per_sample": per_sample, "aggregate": aggregate(per_sample)}
    rate = report["aggregate"]["hit_rate"]
    out = _write_artifacts(report, artifacts_dir)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"报告已归档：{out}", file=sys.stderr)

    if rate is None or rate < HIT_RATE_THRESHOLD:
        print(f"命中率 {rate} 低于阈值 {HIT_RATE_THRESHOLD}，验收失败", file=sys.stderr)
        return 1
    print(f"命中率 {rate:.2%} ≥ {HIT_RATE_THRESHOLD:.0%}，验收通过", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
