"""Inspiration Pydantic schemas（输入/输出契约）。

content 形状按 type 决定，service 层用对应 Pydantic model 校验：
- keyword: {words: [str]}
- plot:    {summary: str, beats: [str] = []}
- snippet: {text: str, source: str | None}
- image:   {description: str}
- note:    {text: str}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.inspiration import INSPIRATION_TYPES

_TYPE_MAX = 20
_SOURCE_MAX = 500
_TAG_MAX = 50
_TAG_COUNT_MAX = 50  # 最多 50 个 tag


# ===== content 子模型 =====


class KeywordContent(BaseModel):
    """关键词灵感。"""

    model_config = ConfigDict(extra="forbid")

    words: list[str] = Field(min_length=1, description="关键词列表")


class PlotContent(BaseModel):
    """情节灵感。"""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=5000, description="情节概述")
    beats: list[str] = Field(default_factory=list, description="关键节拍")


class SnippetContent(BaseModel):
    """片段/句子。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000, description="片段正文")
    source: str | None = Field(default=None, max_length=_SOURCE_MAX, description="出处")


class ImageContent(BaseModel):
    """画面描述。"""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=5000, description="画面描述")


class NoteContent(BaseModel):
    """通用备注。"""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10000, description="备注内容")


# ===== Inspiration 主 schema =====


class InspirationBase(BaseModel):
    """灵感共有字段。"""

    type: str = Field(
        default="note",
        max_length=_TYPE_MAX,
        description=f"灵感类型，取值之一：{', '.join(INSPIRATION_TYPES)}",
    )
    source: str | None = Field(default=None, max_length=_SOURCE_MAX, description="灵感来源")
    tags: list[str] = Field(
        default_factory=list,
        max_length=_TAG_COUNT_MAX,
        description="标签列表",
    )


class InspirationCreate(InspirationBase):
    """创建输入。"""

    novel_id: int | None = Field(default=None, gt=0, description="所属作品 id（None=通用）")
    content: dict[str, Any] = Field(description="灵感内容（dict 形状由 type 决定，service 校验）")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "keyword",
                    "content": {"words": ["修仙", "废柴", "逆袭"]},
                    "tags": ["热门"],
                },
                {"type": "plot", "content": {"summary": "主角身世之谜", "beats": ["幼年目睹"]}},
                {"type": "snippet", "content": {"text": "剑气如虹，一剑破万法。"}},
                {"type": "image", "content": {"description": "云海之巅，一人独立"}},
                {"type": "note", "content": {"text": "某天在地铁上想到的灵感..."}},
            ]
        }
    )


class InspirationUpdate(BaseModel):
    """部分更新。"""

    model_config = ConfigDict(extra="forbid")

    type: str | None = Field(default=None, max_length=_TYPE_MAX)
    source: str | None = Field(default=None, max_length=_SOURCE_MAX)
    tags: list[str] | None = Field(default=None, max_length=_TAG_COUNT_MAX)
    content: dict[str, Any] | None = Field(default=None)
    novel_id: int | None = Field(default=None, gt=0)


class InspirationRead(InspirationBase):
    """API 返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int | None
    content: dict[str, Any]
    created_at: datetime


# ===== Phase 3.3：剧情生成（不入库，仅生成） =====


class PlotGenerationRequest(BaseModel):
    """剧情生成请求。

    注意：本请求**不**持久化到 inspirations 表，结果由调用方决定是否保存。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "genre": "修仙",
                "keywords": ["废柴逆袭", "退婚打脸", "秘境"],
                "n_versions": 3,
            }
        }
    )

    genre: str = Field(min_length=1, max_length=50, description="题材中文名（如 修仙/都市）")
    keywords: list[str] = Field(min_length=1, max_length=50, description="灵感词列表（≥1）")
    n_versions: int = Field(default=3, ge=1, le=10, description="生成版本数（1-10）")


class PlotVersion(BaseModel):
    """单个生成版本。"""

    index: int = Field(description="版本序号（从 1 开始）")
    summary: str = Field(description="剧情概述")


class PlotGenerationResponse(BaseModel):
    """剧情生成响应。"""

    versions: list[PlotVersion]
    provider: str = Field(description="实际使用的 LLM provider")
    model: str = Field(default="", description="实际使用的模型名（可能为空）")
