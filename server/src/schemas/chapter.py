"""Chapter Pydantic schemas（输入/输出契约）。

层级：
- ChapterBase：除 novel_id 外的共有字段
- ChapterCreate：创建输入（必填 novel_id + chapter_number，content 可选）
- ChapterUpdate：部分更新（所有字段可选；不修改正文）
- ChapterContentUpdate：内容更新（会创建新版本；必填 content）
- ChapterRead：API 返回
- ChapterVersionRead：版本历史条目
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from ..models.chapter import CHAPTER_STATUSES, VERSION_TRIGGERS

# 业务上限
_TITLE_MAX = 200
_STATUS_MAX = 20
_TRIGGER_MAX = 30
_CONTENT_MAX = 200_000  # 20 万字符；超长正文分章存
_OUTLINE_MAX = 10_000
_PROMPT_MAX = 50_000
_DIFF_MAX = 200_000


class ChapterBase(BaseModel):
    """章节共有字段。"""

    chapter_number: int = Field(ge=1, le=100_000, description="作品内排序号（从 1 开始）")
    title: str | None = Field(default=None, max_length=_TITLE_MAX, description="章节标题")
    outline: str | None = Field(
        default=None, max_length=_OUTLINE_MAX, description="章节大纲/概要"
    )
    status: str = Field(
        default="outline",
        max_length=_STATUS_MAX,
        description=f"写作状态，取值之一：{', '.join(CHAPTER_STATUSES)}",
    )


class ChapterCreate(ChapterBase):
    """创建输入。

    content 可选：如果提供，创建章节后立即写一条 ``user_create`` 初始版本。
    """

    novel_id: int = Field(gt=0, description="所属作品 id")
    content: str | None = Field(
        default=None, max_length=_CONTENT_MAX, description="初始正文（可选）"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "novel_id": 1,
                "chapter_number": 1,
                "title": "第一章 韩立出生",
                "outline": "韩立出生于贫苦农家，七岁被测出灵根...",
                "content": "七月的青牛镇，烈日当空...",
                "status": "drafting",
            }
        }
    )


class ChapterUpdate(BaseModel):
    """部分更新（只改元数据；正文走 ChapterContentUpdate 走版本化）。"""

    model_config = ConfigDict(extra="forbid")

    chapter_number: int | None = Field(default=None, ge=1, le=100_000)
    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    outline: str | None = Field(default=None, max_length=_OUTLINE_MAX)
    status: str | None = Field(default=None, max_length=_STATUS_MAX)


class ChapterContentUpdate(BaseModel):
    """正文更新（写新版本）。

    每次调用都创建一条 ChapterVersion 记录，parent 指向当前版本。
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=_CONTENT_MAX, description="新正文")
    trigger: str = Field(
        default="user_edit",
        max_length=_TRIGGER_MAX,
        description=f"变更原因，取值之一：{', '.join(VERSION_TRIGGERS)}",
    )
    prompt: str | None = Field(
        default=None, max_length=_PROMPT_MAX, description="触发本次变更的 prompt（LLM 时填）"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="附加元数据（如选区范围、模型名等）"
    )


class ChapterRead(ChapterBase):
    """API 返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    current_version_id: int | None
    word_count: int
    created_at: datetime
    updated_at: datetime


class ChapterVersionRead(BaseModel):
    """版本历史条目。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    parent_version_id: int | None
    content: str
    diff: str | None
    trigger: str
    prompt: str | None
    metadata: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasChoices("metadata_", "metadata")
    )
    word_count: int
    created_at: datetime
