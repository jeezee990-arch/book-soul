"""Outline 业务服务（Phase 1.4 大纲 CRUD）。

设计：
- 一部作品可有多份大纲；按 outline_type 区分模式
- create 时按 outline_type 校验 structure 形状（用对应 Pydantic model）
- 业务规则：作品内同 type 不应重复
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Novel
from ..models.outline import OUTLINE_TYPES, Outline
from ..schemas.outline import (
    CompleteStructure,
    FreedomStructure,
    OutlineCreate,
    OutlineUpdate,
)


def _structure_model_for(outline_type: str) -> type[BaseModel]:
    """按 outline_type 返回对应的 Pydantic model。"""
    if outline_type == "complete":
        return CompleteStructure
    if outline_type == "freedom":
        return FreedomStructure
    raise OutlineValidationError(  # noqa: F821
        f"Unknown outline_type: {outline_type!r}; allowed: {OUTLINE_TYPES}"
    )


class OutlineServiceError(Exception):
    """Service 层基础异常。"""


class OutlineNotFoundError(OutlineServiceError):
    def __init__(self, outline_id: int) -> None:
        super().__init__(f"Outline {outline_id} not found")
        self.outline_id = outline_id


class NovelNotFoundError(OutlineServiceError):
    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class OutlineValidationError(OutlineServiceError):
    """字段取值非法。"""


class OutlineTypeConflictError(OutlineServiceError):
    """作品内已存在同 type 大纲。"""

    def __init__(self, novel_id: int, outline_type: str) -> None:
        super().__init__(f"Novel {novel_id} already has an outline of type {outline_type!r}")
        self.novel_id = novel_id
        self.outline_type = outline_type


class OutlineService:
    """大纲 CRUD 服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_type(outline_type: str | None) -> None:
        if outline_type is not None and outline_type not in OUTLINE_TYPES:
            raise OutlineValidationError(
                f"Invalid outline_type: {outline_type!r}; allowed: {OUTLINE_TYPES}"
            )

    def _validate_structure(self, outline_type: str, structure: dict) -> dict:
        """按 outline_type 校验 structure 形状，返回 validated dict。

        校验前剥掉 ``outline_type`` 字段（避免 extra=forbid 拒掉合法的 discriminator 字段）。
        """
        model = _structure_model_for(outline_type)
        # 剥掉 outline_type 字段（输入可能带，模型不需要）
        cleaned = {k: v for k, v in structure.items() if k != "outline_type"}
        try:
            validated = model.model_validate(cleaned)
        except ValidationError as e:
            raise OutlineValidationError(f"Invalid structure for type {outline_type!r}: {e}") from e
        return validated.model_dump()

    async def _ensure_novel_exists(self, novel_id: int) -> None:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)

    # ===== 业务方法 =====
    async def create(self, data: OutlineCreate) -> Outline:
        """创建大纲。作品内同 type 不应重复。"""
        self._validate_type(data.outline_type)
        await self._ensure_novel_exists(data.novel_id)

        # 校验 structure 形状
        structure = self._validate_structure(data.outline_type, data.structure)
        # 注入 outline_type 字段方便反序列化
        structure["outline_type"] = data.outline_type

        # 校验"作品内同 type 唯一"
        existing = await self.session.execute(
            select(Outline).where(
                Outline.novel_id == data.novel_id,
                Outline.outline_type == data.outline_type,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise OutlineTypeConflictError(data.novel_id, data.outline_type)

        outline = Outline(
            novel_id=data.novel_id,
            outline_type=data.outline_type,
            structure=structure,
        )
        self.session.add(outline)
        await self.session.commit()
        await self.session.refresh(outline)
        return outline

    async def get(self, outline_id: int) -> Outline:
        """按 id 查询；不存在抛 NotFound。"""
        outline = await self.session.get(Outline, outline_id)
        if outline is None:
            raise OutlineNotFoundError(outline_id)
        return outline

    async def list_all(
        self,
        novel_id: int | None = None,
        *,
        outline_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Outline]:
        """列出大纲，支持 novel_id / outline_type 过滤。"""
        self._validate_type(outline_type)
        stmt = select(Outline)
        if novel_id is not None:
            stmt = stmt.where(Outline.novel_id == novel_id)
        if outline_type is not None:
            stmt = stmt.where(Outline.outline_type == outline_type)
        stmt = stmt.order_by(Outline.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, outline_id: int, data: OutlineUpdate) -> Outline:
        """部分更新。改 outline_type 时不迁移 structure（避免数据不一致）。"""
        outline = await self.get(outline_id)
        updates = data.model_dump(exclude_unset=True)
        if "outline_type" in updates:
            self._validate_type(updates["outline_type"])
        if "structure" in updates and updates["structure"] is not None:
            # 用 outline 当前 type（如果没改）校验
            type_to_validate = updates.get("outline_type", outline.outline_type)
            updates["structure"] = self._validate_structure(type_to_validate, updates["structure"])
        for key, value in updates.items():
            setattr(outline, key, value)
        await self.session.commit()
        await self.session.refresh(outline)
        return outline

    async def delete(self, outline_id: int) -> None:
        """删除。幂等。"""
        outline = await self.session.get(Outline, outline_id)
        if outline is not None:
            await self.session.delete(outline)
            await self.session.commit()
