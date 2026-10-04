"""风格解析单测：friendly/stress/deep → 三个 tone 片段（SS-05/07/09）。"""
from __future__ import annotations

import pytest

from app.services.interview.style_resolver import StylePrompts, resolve_style


def test_resolve_friendly():
    p = resolve_style("friendly")
    assert isinstance(p, StylePrompts)
    assert p.system_prompt and p.followup_tone and p.feedback_tone


def test_resolve_unknown_raises():
    with pytest.raises(ValueError):
        resolve_style("rude")


def test_three_styles_distinct():
    f = resolve_style("friendly")
    s = resolve_style("stress")
    d = resolve_style("deep")
    assert len({f.feedback_tone, s.feedback_tone, d.feedback_tone}) == 3


def test_stress_tone_is_critical():
    s = resolve_style("stress")
    assert "薄弱" in s.feedback_tone or "问题" in s.feedback_tone


def test_deep_tone_is_principle():
    d = resolve_style("deep")
    assert "底层" in d.followup_tone or "原理" in d.followup_tone
