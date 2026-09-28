"""prompt_loader 单测：version 头校验、模板加载（QG-07 / SS-07，红线 9）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.prompts.interview import answer_evaluation, follow_up_decision, question_generation
from app.prompts.interview.styles import deep, friendly, stress
from app.services.common.prompt_loader import PromptVersionError, load_template, require_version


def test_require_version_ok():
    assert require_version(question_generation) == "2.1"  # M4-PR2/R7-a v1→v2.1 升级


def test_require_version_missing_raises():
    with pytest.raises(PromptVersionError):
        require_version(SimpleNamespace())


def test_require_version_empty_raises():
    with pytest.raises(PromptVersionError):
        require_version(SimpleNamespace(VERSION=""))


def test_load_template_ok():
    t = load_template(question_generation, "QUESTION_GENERATION_PROMPT")
    assert t.version == "2.1"
    assert "{position}" in t.template


def test_load_template_missing_attr_raises():
    with pytest.raises(PromptVersionError):
        load_template(question_generation, "NON_EXISTENT")


def test_all_interview_prompts_have_version():
    # question_generation 已升 v2.1（M4-PR2/R7-a），其余面试 prompt 仍为 v1.0
    for mod in (answer_evaluation, follow_up_decision, friendly, stress, deep):
        assert require_version(mod) == "1.0"
    assert require_version(question_generation) == "2.1"
