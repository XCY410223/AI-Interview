"""简历对象存储服务：文件名清洗 + 上传（红线 3/8，M1 计划 §4.3/§4.4）。"""
from __future__ import annotations

from app.common.exceptions import ResumeFilenameInvalid, ResumeInvalidExtension, ResumeInvalidMime
from app.common.filename import sanitize_object_key
from app.core.storage import StorageClient


class ResumeStorageService:
    @staticmethod
    def _map_error(exc: ValueError) -> Exception:
        msg = str(exc).lower()
        if "mime" in msg:
            return ResumeInvalidMime()
        if "path separator" in msg:
            return ResumeFilenameInvalid()
        return ResumeInvalidExtension()

    @staticmethod
    async def upload(
        storage: StorageClient, *, user_id: int, filename: str, mime: str, content: bytes
    ) -> str:
        """清洗文件名并上传至对象存储，返回 object_key（不含用户原始文件名）。"""
        try:
            object_key = sanitize_object_key(user_id, filename, mime)
        except ValueError as exc:
            raise ResumeStorageService._map_error(exc) from exc
        await storage.put_object(object_key, content, mime)
        return object_key
