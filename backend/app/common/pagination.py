"""分页工具：page/page_size 解析与校验（上限 100，规范 §8.1）。"""
from __future__ import annotations

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def parse_pagination(page: int = DEFAULT_PAGE, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    """归一化分页参数：page >= 1，1 <= page_size <= 100。"""
    page = max(1, int(page))
    page_size = min(max(1, int(page_size)), MAX_PAGE_SIZE)
    return page, page_size
