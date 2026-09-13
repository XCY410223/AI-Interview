"""上传文件名清洗（红线 3 / 规范 §11.3）：存储名永远 `{user_id}_{uuid}.{ext}`（小写）。

关键不变量（M1 计划 §4.3）：
- 存储 key 永远是 `resumes/{user_id}_{uuid4 hex}.{ext}`；
- 禁止把用户原始文件名拼到路径（原文件名绝不出现）；
- 扩展名 + MIME 白名单双重校验，二者都合法才放行。
"""
from __future__ import annotations

import uuid
from pathlib import PurePosixPath

ALLOWED_EXTS = {"pdf", "docx"}
ALLOWED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB（规范 §11.3 / M1 计划 §4.4）


def sanitize_object_key(user_id: int, original_filename: str, mime: str) -> str:
    """生成对象存储 key：`resumes/{user_id}_{uuid4hex}.{ext}`（小写）。

    - 剥除空字节后取后缀（PurePosixPath.suffix，天然丢弃用户路径成分）；
    - 扩展名与 MIME 均在白名单才放行，否则抛 ValueError；
    - 生成的新名不含路径分隔符 / `..`（双重保险）。
    """
    original_filename = (original_filename or "").replace("\x00", "")
    ext = PurePosixPath(original_filename).suffix.lstrip(".").lower()
    mime = (mime or "").strip().lower()

    if ext not in ALLOWED_EXTS:
        raise ValueError(f"extension not allowed: {ext or '<empty>'}")
    if mime not in ALLOWED_MIMES:
        raise ValueError(f"mime not allowed: {mime}")

    new_name = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    # 双重保险：新名字也不允许出现分隔符（理论上不可能，防御性检查）
    if "/" in new_name or "\\" in new_name or ".." in new_name:
        raise ValueError("sanitized name still contains path separator")
    return f"resumes/{new_name}"
