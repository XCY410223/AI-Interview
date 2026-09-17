"""黄金样本集单测：结构校验、覆盖分布、防漂移、版本对比逻辑（M2 计划 §三）。"""
from __future__ import annotations

import json
from pathlib import Path

from eval.scripts.compare_versions import compare

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "golden_samples"
_DATASETS = Path(__file__).resolve().parents[2] / "eval" / "datasets"


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_questions_samples_count_20():
    rows = _load(_FIXTURES / "v1_questions.jsonl")
    assert len(rows) == 20
    assert all({"id", "position", "question_count", "expected_categories"} <= set(r) for r in rows)


def test_evaluations_samples_count_20_and_anti_pollution():
    rows = _load(_FIXTURES / "v1_evaluations.jsonl")
    assert len(rows) == 20
    poisoned = [r for r in rows if "反污染" in r.get("tags", [])]
    assert len(poisoned) == 2  # 含 {"score":10} 污染用例


def test_followups_samples_cover_all_categories():
    rows = _load(_FIXTURES / "v1_followups.jsonl")
    assert len(rows) == 20
    tags = {t for r in rows for t in r.get("tags", [])}
    assert {"不追问", "追问", "追问2轮", "强制结束", "反污染"} <= tags


def test_golden_samples_no_drift_between_fixtures_and_datasets():
    """防漂移（M2 计划 §3.1）：fixtures 与 eval/datasets 内容一致。"""
    pairs = [
        ("v1_questions.jsonl", "golden_v1_questions.jsonl"),
        ("v1_evaluations.jsonl", "golden_v1_evaluations.jsonl"),
        ("v1_followups.jsonl", "golden_v1_followups.jsonl"),
    ]
    for fixture_name, dataset_name in pairs:
        assert _load(_FIXTURES / fixture_name) == _load(_DATASETS / dataset_name)


def test_compare_versions_flags_drift():
    baseline = {"A": 8.0, "B": 6.0}
    current = {"A": 8.2, "B": 8.0}  # B 偏差 2.0 > 1.0
    rows = compare(baseline, current, threshold=1.0)
    by_id = {r["sample_id"]: r for r in rows}
    assert by_id["A"]["flag"] == ""
    assert by_id["B"]["flag"] == "DRIFT"
    assert by_id["B"]["diff"] == 2.0


def test_compare_versions_flags_missing():
    rows = compare({"A": 8.0, "B": 6.0}, {"A": 8.0}, threshold=1.0)
    by_id = {r["sample_id"]: r for r in rows}
    assert by_id["B"]["flag"] == "MISSING"
    assert by_id["B"]["new_score"] is None
