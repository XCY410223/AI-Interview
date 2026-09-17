"""对比新旧评分（M2 计划 §3.2）：输出对比表，偏差 > threshold 高亮。

用法：
    python eval/scripts/compare_versions.py \
        --baseline artifacts/golden_v1_baseline.json \
        --current artifacts/golden_v2_current.json \
        --threshold 1.0
"""
from __future__ import annotations

import argparse
import json


def _load(path: str) -> dict[str, float]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    out: dict[str, float] = {}
    for row in rows:
        value = row.get("value")
        if isinstance(value, dict) and isinstance(value.get("score"), (int, float)):
            out[row["id"]] = float(value["score"])
    return out


def compare(baseline: dict[str, float], current: dict[str, float], threshold: float) -> list[dict]:
    rows: list[dict] = []
    for sample_id in sorted(baseline):
        old = baseline[sample_id]
        new = current.get(sample_id)
        if new is None:
            rows.append({"sample_id": sample_id, "old_score": old, "new_score": None, "diff": None, "flag": "MISSING"})
            continue
        diff = round(new - old, 2)
        flag = "DRIFT" if abs(diff) > threshold else ""
        rows.append({"sample_id": sample_id, "old_score": old, "new_score": new, "diff": diff, "flag": flag})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--threshold", type=float, default=1.0)
    args = parser.parse_args()

    rows = compare(_load(args.baseline), _load(args.current), args.threshold)
    header = f"{'sample_id':<12} {'old':>6} {'new':>6} {'diff':>7}  flag"
    print(header)
    print("-" * len(header))
    for r in rows:
        new = "-" if r["new_score"] is None else f"{r['new_score']:.1f}"
        diff = "-" if r["diff"] is None else f"{r['diff']:+.1f}"
        print(f"{r['sample_id']:<12} {r['old_score']:>6.1f} {new:>6} {diff:>7}  {r['flag']}")
    drift = [r for r in rows if r["flag"] == "DRIFT"]
    print(f"\n共 {len(rows)} 条，偏差 >{args.threshold} 分 {len(drift)} 条（需人工复盘）")


if __name__ == "__main__":
    main()
