"""prompt_loader 单测：version 头校验、模板加载（QG-07，红线 9）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.prompts.interview import question_generation
from app.services.common.prompt_loader import PromptVersionError, load_template, require_version


def test_require_version_ok():
    assert require_version(question_generation) == "1.0"


def test_require_version_missing_raises():
    with pytest.raises(PromptVersionError):
        require_version(SimpleNamespace())


def test_require_version_empty_raises():
    with pytest.raises(PromptVersionError):
        require_version(SimpleNamespace(VERSION=""))


def test_load_template_ok():
    t = load_template(question_generation, "QUESTION_GENERATION_PROMPT")
    assert t.version == "1.0"
    assert "{position}" in t.template


def test_load_template_missing_attr_raises():
    with pytest.raises(PromptVersionError):
        load_template(question_generation, "NON_EXISTENT")
