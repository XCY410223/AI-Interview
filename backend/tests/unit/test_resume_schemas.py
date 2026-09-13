"""schemas/resume 单测：ParsedResume 冻结契约（M1 计划 §5.4）。"""
import pytest
from pydantic import ValidationError

from app.schemas.resume import ParsedResume, PersonalInfo


def test_parsed_resume_defaults():
    p = ParsedResume()
    assert p.personal.name is None
    assert p.education == []
    assert p.projects == []
    assert p.skills == []
    assert p.summary == ""


def test_parsed_resume_full():
    data = {
        "personal": {"name": "张三", "email": "a@b.com", "phone": "13800000000"},
        "education": [{"school": "清华大学", "major": "计算机", "degree": "本科"}],
        "projects": [{"name": "项目A", "role": "后端", "description": "desc", "tech_stack": ["Python"]}],
        "skills": ["Python", "FastAPI"],
        "summary": "概述",
    }
    p = ParsedResume.model_validate(data)
    assert p.personal.name == "张三"
    assert p.education[0].school == "清华大学"
    assert p.projects[0].tech_stack == ["Python"]


def test_invalid_email_rejected():
    with pytest.raises(ValidationError):
        PersonalInfo(email="not-an-email")


def test_empty_email_normalized_to_none():
    p = PersonalInfo(email="")
    assert p.email is None
