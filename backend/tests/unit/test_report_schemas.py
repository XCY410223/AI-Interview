"""报告 schema 契约单测（M3 计划 §四/§十一）：维度冻结、clamp、总分口径、等级边界。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.report import DIMENSION_KEYS, DIMENSION_LABELS, ReportPayload, grade_of


def test_dimension_keys_frozen_order():
    assert len(DIMENSION_KEYS) == 6
    assert DIMENSION_KEYS[0] == "fundamentals"
    assert DIMENSION_KEYS[-1] == "job_fit"
    assert set(DIMENSION_KEYS) == set(DIMENSION_LABELS)


def test_grade_of_boundaries():
    assert grade_of(9.0) == "优秀"
    assert grade_of(8.5) == "良好"
    assert grade_of(8.0) == "良好"
    assert grade_of(7.0) == "合格"
    assert grade_of(6.99) == "待提升"


def test_normalize_clamp_fill_and_drop():
    p = ReportPayload(
        summary="整体不错",
        dimensions=[
            {"key": "technical_depth", "score": 10.5},  # 越界 → clamp 10.0
            {"key": "fundamentals", "score": 6.0},
            {"key": "extra_unknown", "score": 9.0},     # 多余维度 → 裁剪
        ],
    )
    assert [d.key for d in p.dimensions] == list(DIMENSION_KEYS)
    by_key = {d.key: d.score for d in p.dimensions}
    assert by_key["technical_depth"] == 10.0
    assert by_key["fundamentals"] == 6.0
    assert by_key["project_experience"] == 5.0  # 缺失 → 补齐中性 5.0
    assert "extra_unknown" not in by_key


def test_overall_score_is_mean_and_grade():
    p = ReportPayload(
        summary="x",
        dimensions=[{"key": k, "score": 8.0} for k in DIMENSION_KEYS],
    )
    assert p.overall_score == 8.0
    assert p.grade == "良好"


def test_question_scores_clamped():
    p = ReportPayload(
        summary="x",
        dimensions=[{"key": k, "score": 5.0} for k in DIMENSION_KEYS],
        question_scores=[{"question_index": 0, "round": 0, "question": "q", "score": 11.0}],
    )
    assert p.question_scores[0].score == 10.0


def test_missing_summary_rejected():
    with pytest.raises(ValidationError):
        ReportPayload(dimensions=[{"key": k, "score": 5.0} for k in DIMENSION_KEYS])
