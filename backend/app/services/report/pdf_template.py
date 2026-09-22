"""报告 PDF 的 HTML 模板（M3 计划 §五 PR5）。

只负责拼 HTML 字符串（含内联 SVG 雷达图与 CSS Paged Media 分页），**不 import WeasyPrint**，
确保单测可在无系统库环境断言模板内容（§十一）。
"""
from __future__ import annotations

import html

from app.schemas.report import ReportDetail
from app.services.report.radar_svg import build_radar_svg

_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "WenQuanYi Zen Hei", "Noto Sans CJK SC", sans-serif;
       color: #303133; font-size: 12px; line-height: 1.7; }
.header { text-align: center; margin-bottom: 20px; }
.header h1 { font-size: 22px; margin: 0 0 6px; }
.score-badge { font-size: 30px; font-weight: bold; color: #409EFF; }
.grade-badge { display: inline-block; padding: 2px 12px; border-radius: 12px;
               background: #ecf5ff; color: #409EFF; font-size: 13px; }
.section { margin: 14px 0; padding: 12px 14px; border: 1px solid #ebeef5;
           border-radius: 6px; break-inside: avoid; page-break-inside: avoid; }
.section h2 { font-size: 14px; color: #409EFF; margin: 0 0 8px; }
ul { margin: 0; padding-left: 18px; }
li { margin: 2px 0; }
.radar-wrap { text-align: center; margin: 12px 0; }
.dim-grid { width: 100%; border-collapse: collapse; }
.dim-grid th, .dim-grid td { border: 1px solid #ebeef5; padding: 4px 8px; text-align: left; }
.dim-grid th { background: #f5f7fa; }
.q-item { margin: 10px 0; padding: 10px 12px; border-left: 3px solid #409EFF;
          background: #fafafa; break-inside: avoid; page-break-inside: avoid; }
.q-meta { color: #909399; font-size: 11px; }
"""


def _esc(value: str | None) -> str:
    return html.escape(value or "")


def _fmt_score(score: float | None) -> str:
    return f"{score:.1f}" if score is not None else "—"


def render_report_html(detail: ReportDetail) -> str:
    """把 ReportDetail 渲染为报告 HTML（含内联 SVG 雷达图）。"""
    radar_svg = build_radar_svg([(d.name or d.key, d.score) for d in detail.dimensions])

    dim_rows = "".join(
        f"<tr><td>{_esc(d.name or d.key)}</td><td>{_fmt_score(d.score)}</td>"
        f"<td>{_esc(d.comment)}</td></tr>"
        for d in detail.dimensions
    )

    strengths = "".join(f"<li>{_esc(s)}</li>" for s in detail.strengths) or "<li>—</li>"
    weaknesses = "".join(f"<li>{_esc(w)}</li>" for w in detail.weaknesses) or "<li>—</li>"
    suggestions = "".join(f"<li>{_esc(s)}</li>" for s in detail.suggestions) or "<li>—</li>"

    q_items = "".join(
        '<div class="q-item">'
        f'<div class="q-meta">第 {q.question_index + 1} 题 · 第 {q.round + 1} 轮 · '
        f"评分 {_fmt_score(q.score)}</div>"
        f"<div><b>问题：</b>{_esc(q.question)}</div>"
        f"<div><b>点评：</b>{_esc(q.feedback)}</div></div>"
        for q in detail.question_scores
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>{_CSS}</style></head>
<body>
  <div class="header">
    <h1>面试评估报告</h1>
    <div class="score-badge">{_fmt_score(detail.overall_score)}</div>
    <span class="grade-badge">{_esc(detail.grade) or "—"}</span>
  </div>

  <div class="radar-wrap">{radar_svg}</div>

  <div class="section">
    <h2>能力雷达</h2>
    <table class="dim-grid">
      <tr><th>维度</th><th>得分</th><th>评语</th></tr>
      {dim_rows}
    </table>
  </div>

  <div class="section">
    <h2>整体评价</h2>
    <p>{_esc(detail.summary)}</p>
    {f'<p><b>录用建议：</b>{_esc(detail.hire_recommendation)}</p>' if detail.hire_recommendation else ""}
  </div>

  <div class="section"><h2>优势</h2><ul>{strengths}</ul></div>
  <div class="section"><h2>不足</h2><ul>{weaknesses}</ul></div>
  <div class="section"><h2>改进建议</h2><ul>{suggestions}</ul></div>

  <div class="section">
    <h2>逐题明细</h2>
    {q_items or "<p>—</p>"}
  </div>
</body>
</html>"""
