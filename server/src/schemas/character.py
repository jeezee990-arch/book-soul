"""Character Pydantic schemas（输入/输出契约）。

层级：
- CharacterBase：除 novel_id 外的共有字段
- CharacterCreate：创建输入（必填 novel_id + name + role，其他可选）
- CharacterUpdate：部分更新（所有字段可选）
- CharacterRead：API 返回（含 id、时间戳、current_version_id、is_active、growth_arc）
- CharacterGrowthUpdate：性格/状态变化事件（必填 event，其他字段按需改）
- CharacterVersionRead：版本历史条目
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.character import CHARACTER_ROLES

# 业务上限
_NAME_MAX = 100
_ROLE_MAX = 20
_TEXT_MAX = 5000
_CHANGE_REASON_MAX = 30


class CharacterBase(BaseModel):
    """人物卡共有字段。"""

    name: str = Field(min_length=1, max_length=_NAME_MAX, description="人物名")
    role: str = Field(
        default="其他",
        max_length=_ROLE_MAX,
        description=f"角色定位，取值之一：{', '.join(CHARACTER_ROLES)}",
    )
    basic_info: str | None = Field(default=None, max_length=_TEXT_MAX, description="基本信息")
    personality: str | None = Field(default=None, max_length=_TEXT_MAX, description="性格")
    habits: str | None = Field(default=None, max_length=_TEXT_MAX, description="习惯")
    thinking: str | None = Field(default=None, max_length=_TEXT_MAX, description="思维方式")
    relationships: str | None = Field(default=None, max_length=_TEXT_MAX, description="人物关系")


class CharacterCreate(CharacterBase):
    """创建输入。"""

    novel_id: int = Field(gt=0, description="所属作品 id")
    is_active: bool = Field(default=True, description="是否在用")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "novel_id": 1,
                "name": "韩立",
                "role": "主角",
                "basic_info": "凡人修仙传主角，资质平庸",
                "personality": "谨慎、隐忍、务实",
                "habits": "随身带多件保命法器",
                "thinking": "凡事留后路，不轻易树敌",
                "relationships": "师兄好友：厉飞雨；道侣：南宫婉",
            }
        }
    )


class CharacterUpdate(BaseModel):
    """部分更新（所有字段可选）。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=_NAME_MAX)
    role: str | None = Field(default=None, max_length=_ROLE_MAX)
    basic_info: str | None = Field(default=None, max_length=_TEXT_MAX)
    personality: str | None = Field(default=None, max_length=_TEXT_MAX)
    habits: str | None = Field(default=None, max_length=_TEXT_MAX)
    thinking: str | None = Field(default=None, max_length=_TEXT_MAX)
    relationships: str | None = Field(default=None, max_length=_TEXT_MAX)
    is_active: bool | None = Field(default=None)


class CharacterGrowthUpdate(BaseModel):
    """记录一次"性格/状态变化事件"。

    触发场景：主角经历某事件后性格/习惯/关系发生变化。
    - event 必填：会写入 growth_arc
    - 其他字段（personality / habits / thinking / relationships）按需改
    - 每次调用都会创建一条新版本
    """

    model_config = ConfigDict(extra="forbid")

    event: str = Field(min_length=1, max_length=_TEXT_MAX, description="触发事件描述")
    new_personality: str | None = Field(
        default=None, max_length=_TEXT_MAX, description="事件后新性格（None 不改）"
    )
    new_habits: str | None = Field(default=None, max_length=_TEXT_MAX)
    new_thinking: str | None = Field(default=None, max_length=_TEXT_MAX)
    new_relationships: str | None = Field(default=None, max_length=_TEXT_MAX)


class CharacterRead(CharacterBase):
    """API 返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    growth_arc: str | None
    current_version_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CharacterVersionRead(BaseModel):
    """版本历史条目。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    character_id: int
    parent_version_id: int | None
    snapshot: dict[str, Any]
    change_reason: str
    trigger_event: str | None
    created_at: datetime
