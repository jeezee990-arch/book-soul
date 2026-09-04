"""词库 Pydantic schema（输入/输出契约）。

端点：
- GET /wordbanks          → list[str]                        题材 id 列表
- GET /wordbanks/{genre}  → WordbankMeta                     元数据
- GET /wordbanks/{genre}/words?category=...&n=10            → list[str] | dict
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WordbankMeta(BaseModel):
    """单个题材的词库元数据。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="题材 id（与文件名同名，如 xiuxian）")
    name: str = Field(description="题材中文名（来自 YAML）")
    categories: list[str] = Field(description="所有分类名")
    counts: dict[str, int] = Field(description="每个分类的词数")


class WordbankListEntry(BaseModel):
    """``GET /wordbanks`` 返回的单个题材摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    total: int = Field(description="该题材总词数")


class WordbankList(BaseModel):
    """``GET /wordbanks`` 返回。"""

    genres: list[WordbankListEntry]
