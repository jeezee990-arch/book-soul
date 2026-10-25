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
    # ⚠️ 2026-10-25 巡检（mypy 揪出来的真 bug）：这一列**以前根本没在 schema 里**。
    #    ORM 有 growth_arc 列、prompt 让 LLM 生成、character_generator 也取了值，
    #    但 CharacterCreate 没有这个字段 → Pydantic 默认 extra="ignore" →
    #    **成长弧线被静默丢弃**，导出时"成长弧线"一栏永远是空的。
    #
    #    只加在 Create 上，不加进 CharacterBase：CharacterRead 单独声明了它，
    #    而且 CharacterUpdate 故意不加（growth_arc 由 update_growth 追加维护，
    #    不允许外部直接改 —— 见 character_service 的设计取舍）。
    growth_arc: str | None = Field(
        default=None,
        max_length=_TEXT_MAX,
        description="成长弧线（初始值；后续由 update_growth 追加）",
    )

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
                "growth_arc": "从资质平庸的杂役，一步步修炼到化神。",
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
    # ⚠️ 2026-10-25 巡检（真 bug）：前端人物卡编辑表单**一定会带上** growth_arc，
    #    而这个 schema 之前没有该字段 + extra="forbid" →
    #    PATCH 人物卡一律 422「额外字段不允许」→ **改名字都保存不了**。
    #    ORM 有这一列，表单也在编辑它，所以这里必须收下。
    growth_arc: str | None = Field(default=None, max_length=_TEXT_MAX)
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


# =====================================================================
# Phase 3.5：人物卡自动生成 schemas
# =====================================================================


class ExtractedCharacter(BaseModel):
    """LLM 第一阶段抽取的人物条目（name + role）。"""

    name: str = Field(min_length=1, max_length=_NAME_MAX, description="人物名")
    role: str = Field(
        max_length=_ROLE_MAX,
        description=f"角色定位，取值之一：{', '.join(CHARACTER_ROLES)}",
    )


class CharacterGenerationRequest(BaseModel):
    """人物卡自动生成请求（从大纲生成）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "outline": {
                    "outline_type": "complete",
                    "volumes": [
                        {
                            "name": "第一卷 觉醒",
                            "summary": "主角觉醒血脉、拜入宗门。",
                            "chapters": [],
                        }
                    ],
                },
                "genre": "修仙",
            }
        }
    )

    outline: dict[str, Any] = Field(
        description="大纲 JSON 结构（来自大纲生成端点或手动构造）",
    )
    genre: str = Field(
        default="通用",
        min_length=1,
        max_length=20,
        description="题材（如'修仙'/'都市'/'悬疑'/'言情'）",
    )
    user_extra: str = Field(default="", max_length=2000, description="作者个人想法，会拼进 prompt")


class CharacterGenerationItem(BaseModel):
    """单张生成卡返回（数据库 Character + 关键字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    basic_info: str | None
    personality: str | None
    habits: str | None
    thinking: str | None
    relationships: str | None
    growth_arc: str | None
    is_active: bool


class CharacterGenerationResponse(BaseModel):
    """人物卡自动生成响应。"""

    novel_id: int = Field(description="所属作品 id")
    characters: list[CharacterGenerationItem] = Field(
        description="生成的人物卡列表（已入库 + 初始版本）",
    )
    provider: str = Field(description="LLM provider（用于前端展示）")
    model: str = Field(description="LLM 模型名（用于前端展示）")
