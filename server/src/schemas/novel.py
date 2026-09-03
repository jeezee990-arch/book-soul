"""Novel Pydantic schemas（输入/输出契约）。

层级：
- NovelBase：共有字段
- NovelCreate：创建输入（必填 name + genre，其他可选）
- NovelUpdate：部分更新（所有字段可选）
- NovelRead：API 返回（包含 id + 时间戳）
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.novel import NOVEL_STATUSES, OUTLINE_MODES

# 业务上限
_NAME_MAX = 200
_GENRE_MAX = 50
_STYLE_MAX = 50
_STATUS_MAX = 20
_DESCRIPTION_MAX = 2000
_OUTLINE_MODE_MAX = 20
_FILE_PATH_MAX = 1000


class NovelBase(BaseModel):
    """作品共有字段。"""

    name: str = Field(min_length=1, max_length=_NAME_MAX, description="作品名")
    genre: str = Field(
        min_length=1, max_length=_GENRE_MAX, description="题材（xuanhuan/dushi/...）"
    )
    style: str | None = Field(default=None, max_length=_STYLE_MAX, description="文风")
    description: str | None = Field(default=None, max_length=_DESCRIPTION_MAX, description="简介")
    status: str = Field(
        default="draft",
        max_length=_STATUS_MAX,
        description=f"状态，取值之一：{', '.join(NOVEL_STATUSES)}",
    )
    outline_mode: str | None = Field(
        default=None,
        max_length=_OUTLINE_MODE_MAX,
        description=f"大纲模式，取值之一：{', '.join(OUTLINE_MODES)}",
    )
    file_path: str | None = Field(
        default=None, max_length=_FILE_PATH_MAX, description="本地文件路径（扫描接入时填写）"
    )
    imported: bool = Field(default=False, description="是否扫描接入")
    read_only: bool = Field(default=False, description="是否只读")


class NovelCreate(NovelBase):
    """创建输入。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "我的修仙小说",
                "genre": "xuanhuan",
                "style": "古典",
                "description": "一个少年修仙的故事",
            }
        }
    )


class NovelUpdate(BaseModel):
    """部分更新（所有字段可选）。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=_NAME_MAX)
    genre: str | None = Field(default=None, min_length=1, max_length=_GENRE_MAX)
    style: str | None = Field(default=None, max_length=_STYLE_MAX)
    description: str | None = Field(default=None, max_length=_DESCRIPTION_MAX)
    status: str | None = Field(default=None, max_length=_STATUS_MAX)
    outline_mode: str | None = Field(default=None, max_length=_OUTLINE_MODE_MAX)
    file_path: str | None = Field(default=None, max_length=_FILE_PATH_MAX)
    imported: bool | None = Field(default=None)
    read_only: bool | None = Field(default=None)


class NovelRead(NovelBase):
    """API 返回（包含 id 与时间戳）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
