"""schemas 单测：统一响应与分页、ORM 序列化基类。"""
from app.schemas.base import ORMModel
from app.schemas.common import Page, Response


def test_response_defaults():
    r = Response()
    assert r.code == "OK"
    assert r.message == "success"
    assert r.data is None


def test_response_with_data():
    r = Response[int](data=42)
    assert r.data == 42


def test_page():
    p = Page[int](total=2, items=[1, 2])
    assert p.total == 2
    assert p.items == [1, 2]


def test_orm_model_from_attributes():
    assert ORMModel.model_config.get("from_attributes") is True
