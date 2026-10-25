"""Outline Pydantic schemas（输入/输出契约）。

structure 字段是 dict[str, Any]，具体形状由 outline_type 决定；
service 层用对应 Pydantic model 校验形状（避免 schema 层 discriminated union 复杂性）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.outline import OUTLINE_TYPES

_TYPE_MAX = 20
_SUMMARY_MAX = 10_000
_BEAT_MAX = 500
_THEME_MAX = 200
_VOLUME_NAME_MAX = 100
_CHAPTER_TITLE_MAX = 200
_KEY_EVENT_MAX = 500
_SUSPENSE_MAX = 1000


# ===== structure 子模型（complete / freedom 形状）=====
# 这些不在 OutlineCreate 里直接用（太复杂），由 service 层 validate_structure() 校验
# 但放在这里作为"structure 形状的参考 + 测试可复用"


class ChapterNode(BaseModel):
    """complete 结构里的章节节点。"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=_CHAPTER_TITLE_MAX)
    summary: str | None = Field(default=None, max_length=_SUMMARY_MAX)
    key_events: list[str] = Field(default_factory=list)


class VolumeNode(BaseModel):
    """complete 结构里的卷节点。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=_VOLUME_NAME_MAX)
    summary: str | None = Field(default=None, max_length=_SUMMARY_MAX)
    chapters: list[ChapterNode] = Field(default_factory=list)


class CompleteStructure(BaseModel):
    """完整版大纲：分卷 > 章 > 关键事件。"""

    model_config = ConfigDict(extra="forbid")

    volumes: list[VolumeNode] = Field(default_factory=list, description="分卷列表")
    overall_theme: str | None = Field(default=None, max_length=_THEME_MAX, description="全篇主题")


class FreedomStructure(BaseModel):
    """创作型大纲：自由文字 + 关键节拍 + 主题。"""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=_SUMMARY_MAX, description="大纲文字描述")
    key_beats: list[str] = Field(default_factory=list, description="关键节拍")
    themes: list[str] = Field(default_factory=list, description="主题列表")


class SemiOpenStructure(BaseModel):
    """半开放式大纲：前期分卷 + 悬念钩子。

    与 :class:`CompleteStructure` 的区别只在于**篇幅刻意留短**，并且多一个
    ``suspense_hook``（悬念钩子）字段 —— 它是作者后续创作的起点。
    """

    model_config = ConfigDict(extra="forbid")

    volumes: list[VolumeNode] = Field(default_factory=list, description="前期分卷列表")
    overall_theme: str | None = Field(default=None, max_length=_THEME_MAX, description="全篇主题")
    suspense_hook: str | None = Field(
        default=None, max_length=_SUSPENSE_MAX, description="悬念钩子（大纲在此停下）"
    )


# ===== Outline 主 schema =====


class OutlineBase(BaseModel):
    """大纲共有字段。"""

    outline_type: str = Field(
        default="complete",
        max_length=_TYPE_MAX,
        description=f"大纲模式，取值之一：{', '.join(OUTLINE_TYPES)}",
    )


class OutlineCreate(OutlineBase):
    """创建输入。structure 形状由 outline_type 决定（service 校验）。"""

    novel_id: int = Field(gt=0, description="所属作品 id")
    structure: dict[str, Any] = Field(
        description=(
            "大纲结构（dict）。"
            "complete: 应含 volumes: [...]；"
            "semi_open: 应含 volumes: [...] + suspense_hook: str；"
            "freedom: 应含 summary: str + key_beats: [...]。形状错误会被 service 拒。"
        )
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "novel_id": 1,
                    "outline_type": "complete",
                    "structure": {
                        "volumes": [
                            {
                                "name": "第一卷 凡人篇",
                                "chapters": [{"title": "韩立出生", "key_events": ["测试灵根"]}],
                            }
                        ],
                    },
                },
                {
                    "novel_id": 1,
                    "outline_type": "freedom",
                    "structure": {
                        "summary": "一个凡人修仙的热血故事",
                        "key_beats": ["灵根测试", "拜入宗门", "修为提升"],
                    },
                },
            ]
        }
    )


class OutlineUpdate(BaseModel):
    """部分更新。"""

    model_config = ConfigDict(extra="forbid")

    outline_type: str | None = Field(default=None, max_length=_TYPE_MAX)
    structure: dict[str, Any] | None = Field(default=None)


class OutlineRead(OutlineBase):
    """API 返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    novel_id: int
    structure: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ===== Phase 3.4：基于剧情生成大纲（自动建 novel）=====


class OutlineGenerationRequest(BaseModel):
    """大纲生成请求。

    - 必传 ``plot_summary``（来自 3.3 PlotGenerator 保存的 PLOT 卡 content.summary）
    - ``genre`` 用于 prompt 注入；``keywords`` 可选（让 LLM 知道强调什么）
    - ``novel_name`` 可选（缺省用 "{genre}新作"）
    - ``outline_type`` 取值 ``complete``（分卷/章，完整写到全书结束）、
      ``semi_open``（半开放式：只写前期并留悬念）或 ``freedom``（散文+节拍）

    **规模参数**（2026-10-25 新增）：以前 prompt 把"20-40 章"写死，
    作者在想法里写的"100 章"会被无视。现在规模是显式参数：

    - ``total_chapters``      全书总章数
    - ``chapters_per_volume`` 每卷章数（目标值）
    - ``words_per_chapter``   每章字数
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "genre": "修仙",
                "plot_summary": "主角是灵根被夺的废材...",
                "keywords": ["废柴逆袭", "秘境"],
                "novel_name": "灵根重塑",
                "outline_type": "complete",
                "total_chapters": 100,
                "chapters_per_volume": 10,
                "words_per_chapter": 3000,
            }
        }
    )

    genre: str = Field(min_length=1, max_length=50)
    plot_summary: str = Field(min_length=10, max_length=5000)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    novel_name: str | None = Field(default=None, max_length=200)
    outline_type: str = Field(
        default="complete",
        description=(
            "complete（分卷/章，完整大纲）/ "
            "semi_open（半开放式：只写前期并留悬念）/ "
            "freedom（散文+节拍）"
        ),
    )
    user_extra: str = Field(default="", max_length=2000, description="作者个人想法，会拼进 prompt")
    # ===== 规模参数（硬指标：写进 prompt，模型必须照做）=====
    total_chapters: int = Field(
        default=30,
        ge=1,
        le=500,
        description="全书总章数（硬指标）。",
    )
    chapters_per_volume: int = Field(
        default=10,
        ge=1,
        le=100,
        description="每卷章数（目标值；总章数不能整除时按均分+前几卷多 1 章分配）。",
    )
    words_per_chapter: int = Field(
        default=3000,
        ge=500,
        le=20000,
        description="每章字数。",
    )


class OutlineGenerationResponse(BaseModel):
    """大纲生成响应（含自动建的 novel 信息）。"""

    novel_id: int
    novel_name: str
    outline_id: int
    outline_type: str
    structure: dict[str, Any]
    provider: str
    model: str = ""


class OutlineContinueRequest(BaseModel):
    """AI 辅助续写大纲的请求。

    续写的是**已有大纲的后面**：基于已有卷 + 已写章节，生成后续卷章并追加。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "volume_count": 1,
                "chapters_per_volume": 10,
                "words_per_chapter": 3000,
                "user_extra": "下一卷主角要面对宿敌的复仇",
            }
        }
    )

    volume_count: int = Field(default=1, ge=1, le=5, description="新增几卷")
    chapters_per_volume: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="每卷章数；缺省取已有大纲的平均值",
    )
    words_per_chapter: int = Field(default=3000, ge=500, le=20000, description="每章字数")
    keywords: list[str] = Field(default_factory=list, max_length=50)
    user_extra: str = Field(default="", max_length=2000, description="作者特别要求")
