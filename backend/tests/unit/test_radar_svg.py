"""雷达图 SVG 单测：结构断言与边界（M3 计划 §二 决策 2 / §十一）。"""
from __future__ import annotations

from app.services.report.radar_svg import build_radar_svg

LABELS = ("基础知识", "技术深度", "项目经验", "逻辑思维", "表达沟通", "岗位匹配")


def _dims(*scores):
    return list(zip(LABELS, scores))


def test_six_dimensions_structure():
    svg = build_radar_svg(_dims(8, 7, 6, 9, 8.5, 7.5))
    assert svg.startswith("<svg")
    assert svg.count("<polygon") == 5  # 4 层网格 + 1 数据多边形
    assert svg.count("<line") == 6     # 6 条轴
    assert svg.count("<text") == 6     # 6 个标签
    for label in LABELS:
        assert label in svg


def test_all_zero_and_all_full_are_valid():
    svg_zero = build_radar_svg(_dims(0, 0, 0, 0, 0, 0))
    svg_full = build_radar_svg(_dims(10, 10, 10, 10, 10, 10))
    assert svg_zero.count("<polygon") == 5
    assert svg_full.count("<polygon") == 5


def test_empty_dimensions_returns_empty():
    assert build_radar_svg([]) == ""


def test_out_of_range_scores_clamped():
    # 越界分数（负 / >10）应被 clamp，仍产出结构完整的 SVG
    svg = build_radar_svg(_dims(-3, 15, 5, 5, 5, 5))
    assert svg.count("<polygon") == 5
