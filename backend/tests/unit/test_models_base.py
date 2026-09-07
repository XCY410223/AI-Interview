"""models/base 单测：ORM 基类与 mixin 定义。"""
from sqlalchemy.orm import DeclarativeBase

from app.models.base import Base, PKMixin, SoftDeleteMixin, TimestampMixin


def test_base_is_declarative():
    assert issubclass(Base, DeclarativeBase)


def test_pk_mixin_has_id():
    assert "id" in PKMixin.__annotations__


def test_timestamp_mixin_has_audit_fields():
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__


def test_soft_delete_mixin_has_deleted_at():
    assert "deleted_at" in SoftDeleteMixin.__annotations__
