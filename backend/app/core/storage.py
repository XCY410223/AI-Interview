"""对象存储客户端（规范 §3.3/§11.3）：MinIO(dev)/COS(prod)，S3 协议。

所有业务文件（简历/头像）走对象存储，禁止写本地磁盘（红线 8）。
boto3 为同步 SDK，这里用 asyncio.to_thread 包装为异步接口，避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageClient:
    """S3 协议对象存储封装（boto3），异步化暴露。

    默认按 settings 构建；测试可注入 fake client 或 monkeypatch 方法。
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        bucket: str | None = None,
    ) -> None:
        self._endpoint = endpoint or settings.S3_ENDPOINT
        self._access_key = access_key or settings.S3_ACCESS_KEY
        self._secret_key = secret_key or settings.S3_SECRET_KEY
        self._region = region or settings.S3_REGION
        self._bucket = bucket or settings.S3_BUCKET
        self._s3 = self._build()

    def _build(self):
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
        )

    async def put_object(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._put_object, key, data, content_type)

    def _put_object(self, key: str, data: bytes, content_type: str) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get_object(self, key: str) -> bytes:
        return await asyncio.to_thread(self._get_object, key)

    def _get_object(self, key: str) -> bytes:
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")  # type: ignore[union-attr]
            if code == "NoSuchKey":
                raise FileNotFoundError(key) from exc
            raise
        return resp["Body"].read()

    async def ensure_bucket(self) -> None:
        await asyncio.to_thread(self._ensure_bucket)

    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=self._bucket)


# 惰性单例：避免在 import 期创建 boto3 客户端（无网络时也能 import）
_storage: StorageClient | None = None


def get_storage() -> StorageClient:
    global _storage
    if _storage is None:
        _storage = StorageClient()
    return _storage
