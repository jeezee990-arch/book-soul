"""Inspiration 业务服务（Phase 1.5 灵感库 CRUD）。

设计：
- novel_id 可空：通用灵感（novel_id=None）vs 作品灵感
- 不分版本：灵感不演化
- content 按 type 校验形状（service 层用对应 Pydantic model）
- tags 简单 list[str]
- 排序：置顶优先 → sort_order → 创建时间倒序（2026-10-29 素材库管理）

剧情生成（Phase 3.3）已独立成 ``plot_service.py``；这里保留 re-export，
兼容旧 import 路径（老代码和测试还在从本模块导入 ``PlotService``）。
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.inspiration import INSPIRATION_TYPES, Inspiration
from ..models.novel import Novel
from ..schemas.inspiration import (
    ImageContent,
    InspirationCreate,
    InspirationUpdate,
    KeywordContent,
    NoteContent,
    PlotContent,
    SnippetContent,
)

# 兼容旧 import 路径：剧情生成早已独立成模块，但老代码/测试还从这里导入
from .plot_service import (  # noqa: F401
    PlotGenerationError,
    PlotService,
    _strip_thinking,
)


def _content_model_for(inspiration_type: str) -> type[BaseModel]:
    """按 type 返回对应的 content Pydantic model。"""
    if inspiration_type == "keyword":
        return KeywordContent
    if inspiration_type == "plot":
        return PlotContent
    if inspiration_type == "snippet":
        return SnippetContent
    if inspiration_type == "image":
        return ImageContent
    if inspiration_type == "note":
        return NoteContent
    raise InspirationValidationError(  # noqa: F821
        f"Unknown type: {inspiration_type!r}; allowed: {INSPIRATION_TYPES}"
    )


def _tag_like_pattern(tag: str) -> str:
    """把 tag 转成 SQL LIKE 模式，匹配 SQLAlchemy 存 JSON 的实际格式。

    SQLAlchemy 存 JSON 数组用 ensure_ascii=True（``json.dumps`` 默认），
    所以 `["热门"]` 存为 `["\\u70ed\\u95e8"]`。我们要 LIKE 的话也得用
    同样的转义形式。
    """
    inner = json.dumps([tag], ensure_ascii=True)[1:-1]  # 去掉 []
    return f"%{inner}%"


class InspirationServiceError(Exception):
    """Service 层基础异常。"""


class InspirationNotFoundError(InspirationServiceError):
    def __init__(self, inspiration_id: int) -> None:
        super().__init__(f"Inspiration {inspiration_id} not found")
        self.inspiration_id = inspiration_id


class NovelNotFoundError(InspirationServiceError):
    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class InspirationValidationError(InspirationServiceError):
    """字段取值非法。"""


class InspirationService:
    """灵感库 CRUD 服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_type(inspiration_type: str | None) -> None:
        if inspiration_type is not None and inspiration_type not in INSPIRATION_TYPES:
            raise InspirationValidationError(
                f"Invalid type: {inspiration_type!r}; allowed: {INSPIRATION_TYPES}"
            )

    def _validate_content(self, inspiration_type: str, content: dict) -> dict:
        """按 type 校验 content 形状，返回 validated dict（不含 None 字段）。"""
        model = _content_model_for(inspiration_type)
        try:
            validated = model.model_validate(content)
        except ValidationError as e:
            raise InspirationValidationError(
                f"Invalid content for type {inspiration_type!r}: {e}"
            ) from e
        return validated.model_dump(exclude_none=True)

    async def _ensure_novel_exists_if_given(self, novel_id: int | None) -> None:
        if novel_id is not None:
            novel = await self.session.get(Novel, novel_id)
            if novel is None:
                raise NovelNotFoundError(novel_id)

    # ===== 业务方法 =====
    async def create(self, data: InspirationCreate) -> Inspiration:
        """创建灵感。"""
        self._validate_type(data.type)
        await self._ensure_novel_exists_if_given(data.novel_id)
        content = self._validate_content(data.type, data.content)

        inspiration = Inspiration(
            novel_id=data.novel_id,
            type=data.type,
            content=content,
            source=data.source,
            tags=list(data.tags),
            # ⚠️ 2026-10-29 评审：以前漏传 title —— schema 声明了、前端也发了，
            #    但入库时直接丢掉（响应里 title 恒为 null）。
            title=data.title,
        )
        self.session.add(inspiration)
        await self.session.commit()
        await self.session.refresh(inspiration)
        return inspiration

    async def get(self, inspiration_id: int) -> Inspiration:
        """按 id 查询；不存在抛 NotFound。"""
        inspiration = await self.session.get(Inspiration, inspiration_id)
        if inspiration is None:
            raise InspirationNotFoundError(inspiration_id)
        return inspiration

    async def list_all(
        self,
        *,
        novel_id: int | None = None,
        inspiration_type: str | None = None,
        tag: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Inspiration]:
        """列出灵感，支持 novel_id / type / tag 过滤。"""
        self._validate_type(inspiration_type)
        stmt = select(Inspiration)
        # novel_id 过滤：None = **不过滤**（通用 + 所有作品的素材）；
        # int = 只看该作品的
        if novel_id is not None:
            stmt = stmt.where(Inspiration.novel_id == novel_id)
        if inspiration_type is not None:
            stmt = stmt.where(Inspiration.type == inspiration_type)
        # tag 过滤用 JSON LIKE（SQLite 简单实现；转义保证中英文都能匹配）
        if tag is not None:
            stmt = stmt.where(Inspiration.tags.like(_tag_like_pattern(tag)))
        # 排序：置顶优先 → 手动排序 → 创建时间倒序
        stmt = (
            stmt.order_by(
                Inspiration.pinned.desc(),
                Inspiration.sort_order.asc(),
                Inspiration.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, inspiration_id: int, data: InspirationUpdate) -> Inspiration:
        """部分更新。改 type 时要重新校验 content。"""
        inspiration = await self.get(inspiration_id)
        updates = data.model_dump(exclude_unset=True)
        if "type" in updates:
            self._validate_type(updates["type"])
        if "novel_id" in updates:
            await self._ensure_novel_exists_if_given(updates["novel_id"])
        if "content" in updates and updates["content"] is not None:
            # 用最终 type 校验（可能同时改了 type）
            type_to_validate = updates.get("type", inspiration.type)
            updates["content"] = self._validate_content(type_to_validate, updates["content"])
        for key, value in updates.items():
            setattr(inspiration, key, value)
        await self.session.commit()
        await self.session.refresh(inspiration)
        return inspiration

    async def delete(self, inspiration_id: int) -> None:
        """删除。幂等。"""
        inspiration = await self.session.get(Inspiration, inspiration_id)
        if inspiration is not None:
            await self.session.delete(inspiration)
            await self.session.commit()

    async def batch_delete(self, inspiration_ids: Sequence[int]) -> int:
        """批量删除。

        :param inspiration_ids: 待删除的 id 列表（重复 id 自动去重）
        :return: 实际删除条数（不存在的 id 不计入）
        """
        unique_ids = list(dict.fromkeys(inspiration_ids))
        if not unique_ids:
            return 0
        result = await self.session.execute(
            select(Inspiration).where(Inspiration.id.in_(unique_ids))
        )
        rows = list(result.scalars())
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()
        return len(rows)

    async def reorder(self, inspiration_ids: Sequence[int]) -> list[Inspiration]:
        """按给定顺序重排（``sort_order`` = 下标）。

        :param inspiration_ids: 用户拖拽后的显示顺序
        :return: 按新顺序排列的灵感列表（不存在的 id 自动跳过）
        """
        unique_ids = list(dict.fromkeys(inspiration_ids))
        if not unique_ids:
            return []
        result = await self.session.execute(
            select(Inspiration).where(Inspiration.id.in_(unique_ids))
        )
        rows = {row.id: row for row in result.scalars()}
        ordered: list[Inspiration] = []
        for index, inspiration_id in enumerate(unique_ids):
            row = rows.get(inspiration_id)
            if row is None:
                continue
            row.sort_order = index
            ordered.append(row)

        # ⚠️ 2026-10-29 评审：没在列表里的条目必须**推到后面**。
        #    前端一次最多只能拉 500 条（后端 limit 上限），超过的那些
        #    sort_order 会一直是 0 → 排序时（sort_order ASC）跳到最前面，
        #    把用户刚拖好的顺序搅乱。
        #    现在给它们排到已排序条目之后（相对次序保持不变）。
        others_stmt = (
            select(Inspiration)
            .where(Inspiration.id.notin_(unique_ids))
            .order_by(Inspiration.sort_order.asc(), Inspiration.created_at.desc())
        )
        others = list((await self.session.execute(others_stmt)).scalars())
        offset = len(ordered)
        for i, row in enumerate(others):
            row.sort_order = offset + i

        await self.session.commit()
        return ordered
