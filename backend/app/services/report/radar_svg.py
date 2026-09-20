"""纯 Python 生成内联 SVG 雷达图（M3 计划 §二 决策 2）。

零新增依赖：雷达图本质是「6 条轴 + N 层同心多边形 + 1 个数据多边形 + 文字标签」，
用三角函数算坐标拼 SVG 字符串。WeasyPrint 支持 SVG，输出为矢量，PDF 内任意缩放清晰。
前端 ECharts 负责交互展示，本模块只负责 PDF 输出，两者共用同一份维度数据与定义。
"""
from __future__ import annotations

import math


def build_radar_svg(
    dimensions: list[tuple[str, float]],
    size: int = 420,
    max_score: float = 10.0,
) -> str:
    """把 N 个维度渲染成内联 SVG 雷达图。

    dimensions: [(中文标签, 分数 0~10), ...]，顺序固定，长度 ≥3。
    """
    if not dimensions:
        return ""
    n = len(dimensions)
    cx = cy = size / 2
    radius = size * 0.34
    max_score = max(max_score, 1e-6)

    def point(i: int, ratio: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * i / n  # 首轴指向正上方
        return cx + radius * ratio * math.cos(angle), cy + radius * ratio * math.sin(angle)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">']
    # 同心网格（4 层）
    for level in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, level) for i in range(n)))
        parts.append(f'<polygon points="{pts}" fill="none" stroke="#DCDFE6" stroke-width="1"/>')
    # 轴线 + 标签
    for i, (label, _) in enumerate(dimensions):
        x, y = point(i, 1.0)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#DCDFE6" stroke-width="1"/>'
        )
        lx, ly = point(i, 1.22)
        anchor = "middle" if abs(lx - cx) < 1 else ("start" if lx > cx else "end")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="12" fill="#606266" '
            f'text-anchor="{anchor}" dominant-baseline="middle">{label}</text>'
        )
    # 数据多边形
    data_pts = " ".join(
        f"{x:.1f},{y:.1f}"
        for x, y in (
            point(i, max(0.0, min(score, max_score)) / max_score)
            for i, (_, score) in enumerate(dimensions)
        )
    )
    parts.append(
        f'<polygon points="{data_pts}" fill="rgba(64,158,255,0.25)" '
        f'stroke="#409EFF" stroke-width="2"/>'
    )
    parts.append("</svg>")
    return "".join(parts)
