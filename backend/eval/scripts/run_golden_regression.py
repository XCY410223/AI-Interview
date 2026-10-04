"""黄金样本回归脚本（M2 计划 §3.2）：跑 20 条样本并输出结果 JSON。

用法：
    python eval/scripts/run_golden_regression.py \
        --dataset eval/datasets/golden_v1_followups.jsonl \
        --kind followups --output artifacts/golden_v1_followups.json

kind ∈ {questions, evaluations, followups}。调用真实 LLM（需配置 LLM_API_KEY），
judge 配置见 eval/judge/judge_config.py（温度锁死）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from eval.judge.judge_config import JUDGE_CONFIG
from app.schemas.interview import QuestionItem
from app.services.interview.ai_service import InterviewAIService
from app.services.interview.style_resolver import resolve_style


def _load_dataset(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


async def _run(rows: list[dict], kind: str) -> list[dict]:
    service = InterviewAIService()
    results: list[dict] = []
    for row in rows:
        start = time.perf_counter()
        try:
            if kind == "questions":
                qs = await service.generate_questions(
                    position=row["position"], difficulty=row.get("difficulty", "medium"),
                    resume_summary=row.get("resume_summary", ""), question_count=row.get("question_count", 8),
                )
                value = [q.model_dump() for q in qs]
            elif kind == "evaluations":
                q = QuestionItem(question_index=0, category="项目", content=row["question"],
                                 reference_points=row.get("reference_points", []), difficulty="medium")
                s = await service.evaluate_score(question=q, answer=row["answer"])
                value = {"score": s.score, "dimensions": s.dimensions, "feedback": s.feedback}
            else:  # followups
                q = QuestionItem(question_index=0, category="项目", content=row["question"],
                                 reference_points=[], difficulty="medium")
                d = await service.decide_follow_up(
                    question=q, answer_history=row.get("answer_history", []),
                    current_round=row.get("round", 0), style=resolve_style("friendly"),
                )
                value = {"need_follow_up": d.need_follow_up, "follow_up_hint": d.follow_up_hint, "reason": d.reason}
            status = "ok"
        except Exception as exc:  # 单条失败不阻断全量（记录 status）
            value = None
            status = f"error: {exc}"
        results.append({
            "id": row["id"], "kind": kind, "status": status, "value": value,
            "duration_ms": int((time.perf_counter() - start) * 1000),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--kind", required=True, choices=["questions", "evaluations", "followups"])
    parser.add_argument("--output", default="artifacts/golden_regression.json")
    args = parser.parse_args()

    rows = _load_dataset(args.dataset)
    print(f"judge={JUDGE_CONFIG['model']} temperature={JUDGE_CONFIG['temperature']}")
    print(f"dataset={args.dataset} kind={args.kind} samples={len(rows)}")
    results = asyncio.run(_run(rows, args.kind))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {out}")


if __name__ == "__main__":
    main()
