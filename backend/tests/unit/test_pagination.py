"""common/pagination 单测：归一化 page/page_size 与 100 上限（§8.1）。"""
from app.common.pagination import parse_pagination


def test_defaults():
    assert parse_pagination() == (1, 20)


def test_clamps_page_size_to_100():
    assert parse_pagination(1, 500) == (1, 100)


def test_clamps_page_to_at_least_1():
    assert parse_pagination(0, 20) == (1, 20)
    assert parse_pagination(-3, 20) == (1, 20)
