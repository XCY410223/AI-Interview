"""报告 PDF 模板单测：HTML 含 6 维、内联 SVG、分节、转义（M3 计划 §五/§十一）。"""
from __future__ import annotations

from app.schemas.report import DimensionScore, QuestionScore, ReportDetail
from app.services.report.pdf_template import render_report_html

_DIM_PAIRS = (
    ("fundamentals", "基础知识"),
    ("technical_depth", "技术深度"),
    ("project_experience", "项目经验"),
    ("logical_thinking", "逻辑思维"),
    ("communication", "表达沟通"),
    ("job_fit", "岗位匹配"),
)


def _detail() -> ReportDetail:
    return ReportDetail(
        report_id=1,
        interview_id=1,
        status="completed",
        overall_score=8.2,
        grade="良好",
        summary="整体表现不错",
        dimensions=[DimensionScore(key=k, name=n, score=8.0, comment="尚可") for k, n in _DIM_PAIRS],
        strengths=["基础扎实"],
        weaknesses=["项目深度不足"],
        suggestions=["多复盘项目"],
        hire_recommendation="推荐",
        question_scores=[QuestionScore(question_index=0, round=0, question="介绍项目", score=8.0, feedback="不错")],
    )


def test_html_contains_six_dimensions_and_svg():
    html = render_report_html(_detail())
    for _, name in _DIM_PAIRS:
        assert name in html
    assert "<svg" in html
    assert "面试评估报告" in html


def test_html_contains_sections_and_question_detail():
    html = render_report_html(_detail())
    for section in ("整体评价", "优势", "不足", "改进建议", "逐题明细"):
        assert section in html
    assert "介绍项目" in html


def test_html_escapes_special_chars():
    detail = _detail()
    detail.summary = '包含 <script>alert(1)</script> 的总结'
    html = render_report_html(detail)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
