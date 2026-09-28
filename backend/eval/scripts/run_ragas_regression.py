"""Ragas 回归脚本（M4 PR-R6，spec §9.7）。

指标裁剪（spec §9.7 表格逐条执行）：
- ✅ context_precision / context_recall：top-K 命中公司+岗位（纯检索，无 LLM 费用）；
- ✅ faithfulness：改写题忠于原真题（Ragas + DeepSeek judge，t=0，真实跑分交人工）；
- ✅ aspect_critique 自定义：JD 关键词命中率、难度适配度；
- ❌ answer_relevancy / answer_correctness（本场景无标准 Q&A，不实现）。

退出阈值：context_precision ≥ 0.8、faithfulness ≥ 0.9；不达标先调 chunk/embedding/rerank 再上线。

红线 10：ragas 仅在 requirements-dev.txt；本模块 lazy import ragas（纯函数可脱离 ragas 单测）。
judge 配置（DeepSeek + t=0）锁死，见 eval/judge/judge_config.py（只读不改）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

METRIC_THRESHOLDS = {
    "context_precision": 0.8,
    "faithfulness": 0.9,
}

_TUNING_ADVICE = {
    "context_precision": "检索命中率不达标：优先调整切片窗口（300~500）、检索 top-K、或加 rerank；黄金数据集即为调参标尺（§9.7）。",
    "faithfulness": "改写忠实度不达标：检查真题改写 prompt 纪律（禁照搬/适配简历），必要时收紧改写温度与样例。",
}


def load_dataset(path: str | Path) -> list[dict]:
    """加载 RAG 黄金样本（JSONL），忽略空行与非法行。"""
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


def retrieval_precision_recall(
    retrieved_ids: list[int],
    expected_ids: list[int],
    k: int,
) -> dict:
    """top-K 检索命中率：precision = 命中数 / K，recall = 命中数 / 期望数（纯函数）。"""
    retrieved = set(retrieved_ids[:k])
    expected = set(expected_ids)
    hit = len(retrieved & expected)
    return {
        "precision": (hit / k) if k > 0 else 0.0,
        "recall": (hit / len(expected)) if expected else 0.0,
        "hit": hit,
    }


def evaluate_thresholds(metrics: dict) -> dict:
    """阈值判定 + 调参建议（纯函数）：返回通过与否与逐项明细。"""
    checks: list[dict] = []
    passed = True
    for metric, threshold in METRIC_THRESHOLDS.items():
        value = metrics.get(metric)
        ok = value is not None and value >= threshold
        passed = passed and ok
        checks.append({"metric": metric, "value": value, "threshold": threshold, "ok": ok})
    advice = [v for k, v in _TUNING_ADVICE.items() if not any(c["ok"] for c in checks if c["metric"] == k)]
    return {"passed": passed, "checks": checks, "advice": advice}


def _run_ragas_faithfulness(dataset: list[dict]) -> list[float]:
    """Ragas faithfulness（lazy import）：改写题忠于原真题，DeepSeek judge t=0。真实跑分交人工。"""
    from ragas import evaluate
    from ragas.metrics import faithfulness

    # 组装 Ragas Dataset：contexts=原真题，answer=改写题，ground_truth=原真题
    data_samples = {
        "question": [s.get("position", "") for s in dataset],
        "answer": [s.get("rewritten_question", "") for s in dataset],
        "contexts": [s.get("real_questions", []) for s in dataset],
        "ground_truth": [s.get("real_questions", []) for s in dataset],
    }
    from datasets import Dataset

    result = evaluate(Dataset.from_dict(data_samples), metrics=[faithfulness])
    return [float(v) for v in result.get("faithfulness", [])]


def _write_artifacts(report: dict, artifacts_dir: Path) -> Path:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out = artifacts_dir / "ragas_regression_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dataset_path = Path(argv[0]) if argv else Path("eval/datasets/rag_golden_v1.jsonl")
    artifacts_dir = Path(argv[1]) if len(argv) > 1 else Path("artifacts")

    dataset = load_dataset(dataset_path)

    # 检索命中率（纯计算；真实检索结果由调用方注入 sample["retrieved_item_ids"]）
    precisions: list[float] = []
    recalls: list[float] = []
    for s in dataset:
        pr = retrieval_precision_recall(
            s.get("retrieved_item_ids", []),
            s.get("expected_item_ids", []),
            k=s.get("k", 8),
        )
        precisions.append(pr["precision"])
        recalls.append(pr["recall"])

    context_precision = sum(precisions) / len(precisions) if precisions else 0.0
    context_recall = sum(recalls) / len(recalls) if recalls else 0.0

    # faithfulness（Ragas，真实跑分；样本缺 rewritten_question 时跳过，交人工补跑）
    faithfulness_values = _run_ragas_faithfulness(dataset) if any(s.get("rewritten_question") for s in dataset) else []
    faithfulness_score = sum(faithfulness_values) / len(faithfulness_values) if faithfulness_values else None

    metrics = {"context_precision": context_precision, "context_recall": context_recall, "faithfulness": faithfulness_score}
    verdict = evaluate_thresholds(metrics)
    report = {"metrics": metrics, "verdict": verdict}
    out = _write_artifacts(report, artifacts_dir)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"报告已归档：{out}", file=sys.stderr)

    if verdict["passed"]:
        print("Ragas 回归达标", file=sys.stderr)
        return 0
    print("Ragas 回归不达标，调参建议：" + " ".join(verdict["advice"]), file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
