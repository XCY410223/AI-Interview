"""schema 基类（对应参考项目 schemas/base.py）。"""
from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """ORM 序列化基类。"""

    model_config = ConfigDict(from_attributes=True)
