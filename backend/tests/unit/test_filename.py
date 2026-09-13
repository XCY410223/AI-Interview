"""common/filename 单测：路径穿越/中文/MIME 伪造/空字节（红线 3 / M1 计划 §4.5）。"""
from __future__ import annotations

import pytest

from app.common.filename import MAX_FILE_SIZE_BYTES, sanitize_object_key

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_sanitize_returns_safe_key():
    key = sanitize_object_key(1, "简历.pdf", PDF)
    assert key.startswith("resumes/1_")
    assert key.endswith(".pdf")
    # 除前缀 resumes/ 外无路径分隔符
    assert "/" not in key[len("resumes/"):]
    assert ".." not in key


def test_path_traversal_without_ext_rejected():
    with pytest.raises(ValueError):
        sanitize_object_key(1, "../../../etc/passwd", PDF)


def test_path_traversal_with_ext_discards_path():
    key = sanitize_object_key(1, "../../../etc/evil.pdf", PDF)
    assert ".." not in key
    assert "etc" not in key
    assert key.startswith("resumes/1_")


def test_chinese_filename_not_in_key():
    key = sanitize_object_key(1, "中文简历.pdf", PDF)
    assert "中文" not in key


def test_null_byte_stripped():
    key = sanitize_object_key(1, "file\x00.pdf", PDF)
    assert key.endswith(".pdf")


def test_exe_rejected():
    with pytest.raises(ValueError):
        sanitize_object_key(1, "file.exe", PDF)


def test_uppercase_ext_lowercased():
    key = sanitize_object_key(1, "file.PDF", PDF)
    assert key.endswith(".pdf")


def test_mime_ext_double_validation():
    with pytest.raises(ValueError):
        sanitize_object_key(1, "image.png", PDF)  # 扩展名非白名单
    with pytest.raises(ValueError):
        sanitize_object_key(1, "file.pdf", "text/plain")  # MIME 伪造


def test_docx_accepted():
    key = sanitize_object_key(1, "resume.docx", DOCX)
    assert key.endswith(".docx")


def test_max_file_size_is_10mb():
    assert MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
