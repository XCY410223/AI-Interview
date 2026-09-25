"""Ragas 回归脚本纯函数单测（M4 PR-R6）：数据集加载 / 检索命中率 / 阈值判定。"""
from __future__ import annotations

import json

from eval.scripts.run_ragas_regression import (
    evaluate_thresholds,
    load_dataset,
    retrieval_precision_recall,
)


def test_retrieval_precision_recall_full_hit():
    r = retrieval_precision_recall([1, 2, 3, 4, 5, 6, 7, 8], [1, 2], k=8)
    assert r["hit"] == 2
    assert r["precision"] == 2 / 8
    assert r["recall"] == 1.0


def test_retrieval_precision_recall_partial():
    r = retrieval_precision_recall([1, 9, 10, 11, 12, 13, 14, 15], [1, 2], k=8)
    assert r["hit"] == 1
    assert r["recall"] == 0.5


def test_retrieval_precision_recall_empty_expected():
    r = retrieval_precision_recall([1, 2], [], k=8)
    assert r["recall"] == 0.0


def test_evaluate_thresholds_pass():
    verdict = evaluate_thresholds({"context_precision": 0.9, "faithfulness": 0.95})
    assert verdict["passed"] is True
    assert all(c["ok"] for c in verdict["checks"])


def test_evaluate_thresholds_fail_with_advice():
    verdict = evaluate_thresholds({"context_precision": 0.5, "faithfulness": 0.9})
    assert verdict["passed"] is False
    assert any("检索命中率" in a for a in verdict["advice"])


def test_evaluate_thresholds_missing_metric_fails():
    verdict = evaluate_thresholds({"context_precision": 0.9})
    assert verdict["passed"] is False


def test_load_dataset_skips_invalid(tmp_path):
    path = tmp_path / "rag.jsonl"
    path.write_text(
        json.dumps({"company": "字节", "expected_item_ids": [1]}) + "\n\nbad-line\n" +
        json.dumps({"company": "阿里", "expected_item_ids": [2]}) + "\n",
        encoding="utf-8",
    )
    samples = load_dataset(path)
    assert len(samples) == 2
