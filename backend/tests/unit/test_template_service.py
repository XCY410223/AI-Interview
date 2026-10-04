"""题库模板服务单测（M4 PR-R7-a）：CRUD / 出题引用 usage_count 计数。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.common.exceptions import QuestionBankNotFound
from app.services.question_bank.template_service import TemplateService
from tests.fakes import FakeSession


def run(coro):
    return asyncio.run(coro)


def _template(template_id=1, position="后端", difficulty="medium", content="模板题", usage_count=0):
    return SimpleNamespace(
        id=template_id, position=position, difficulty=difficulty, category="项目",
        content=content, reference_points=None, tags=None, usage_count=usage_count,
        created_at=None, updated_at=None, deleted_at=None,
    )


def test_create():
    session = FakeSession()
    t = run(TemplateService.create(
        session, position="后端", difficulty="medium", category="项目",
        content="题", reference_points=[], tags=[],
    ))
    assert session.added == [t]
    assert t.usage_count == 0


def test_get_not_found_raises():
    session = FakeSession().configure(get_map={})
    with pytest.raises(QuestionBankNotFound):
        run(TemplateService.get(session, template_id=99))


def test_get_ok():
    t = _template()
    session = FakeSession().configure(get_map={1: t})
    assert run(TemplateService.get(session, template_id=1)) is t


def test_list_for_generation_increments_usage():
    t1 = _template(template_id=1, content="题1")
    t2 = _template(template_id=2, content="题2")
    session = FakeSession().configure(scalars=[t1, t2])
    contents = run(TemplateService.list_for_generation(session, position="后端", difficulty="medium"))
    assert contents == ["题1", "题2"]
    assert t1.usage_count == 1
    assert t2.usage_count == 1


def test_delete_soft_deletes():
    t = _template()
    session = FakeSession().configure(get_map={1: t})
    run(TemplateService.delete(session, template=t))
    assert t.deleted_at is not None


def test_list_templates():
    t1 = _template(template_id=2)
    t2 = _template(template_id=1)
    session = FakeSession().configure(scalars=[t1, t2], scalar_one=2)
    total, items = run(TemplateService.list_templates(session))
    assert total == 2
    assert [i.id for i in items] == [2, 1]


def test_update():
    t = _template()
    session = FakeSession().configure(get_map={1: t})
    updated = run(TemplateService.update(
        session, template=t, content="新题", difficulty="hard", tags=["x"],
    ))
    assert updated.content == "新题"
    assert updated.difficulty == "hard"
    assert updated.tags == ["x"]
