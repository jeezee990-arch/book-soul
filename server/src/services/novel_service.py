"""Novel 业务服务（Phase 1.1 作品 CRUD）。

设计：
- Service 不依赖 FastAPI，便于单测和复用
- 所有 DB 操作走 SQLAlchemy 2.x AsyncSession
- 输入校验：status / outline_mode 取值用 models.novel 里的常量
- 错误用领域异常（NotFoundError / ValidationError），由 api 层映射到 HTTP

作品名唯一（2026-10-30）
----------------------
同一时间只能有一本同名作品：名字是用户在素材库里识别作品的主要依据，
出现两本「修仙新作」时用户根本分不清哪本是自己刚写的那本。

- ``create`` / ``update`` 改名时撞名 → 抛 :class:`NovelNameConflictError`（API 映射 409）
- 需要"自动避开重名"的场景（开新书的自动命名、批量导入）→ 用 :meth:`NovelService.unique_name`
  拿到一个没人用的名字（``修仙新作`` → ``修仙新作 2`` → ``修仙新作 3`` …）
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import NOVEL_STATUSES, OUTLINE_MODES, Novel
from ..schemas.novel import NovelCreate, NovelUpdate


class NovelServiceError(Exception):
    """Service 层基础异常。"""


class NovelNotFoundError(NovelServiceError):
    """作品不存在。"""

    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class NovelValidationError(NovelServiceError):
    """输入字段取值非法。"""


class NovelNameConflictError(NovelServiceError):
    """作品名已被另一本作品占用。"""

    def __init__(self, name: str) -> None:
        super().__init__(f"已有同名作品：{name}")
        self.name = name


class NovelService:
    """作品 CRUD 服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_status(status: str | None) -> None:
        if status is not None and status not in NOVEL_STATUSES:
            raise NovelValidationError(f"Invalid status: {status!r}; allowed: {NOVEL_STATUSES}")

    @staticmethod
    def _validate_outline_mode(mode: str | None) -> None:
        if mode is not None and mode not in OUTLINE_MODES:
            raise NovelValidationError(f"Invalid outline_mode: {mode!r}; allowed: {OUTLINE_MODES}")

    # ===== 名字查重 =====
    async def name_taken(self, name: str, *, exclude_id: int | None = None) -> bool:
        """同名作品是否已存在。

        :param name: 作品名（调用方先 strip）
        :param exclude_id: 排除自身（改名时用）
        :return: True 表示已经有别的书用了这个名字
        """
        stmt = select(Novel.id).where(Novel.name == name)
        if exclude_id is not None:
            stmt = stmt.where(Novel.id != exclude_id)
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def unique_name(self, base: str) -> str:
        """返回一个**没人占用**的作品名。

        规则：``base`` → ``base 2`` → ``base 3`` …（一直往下找）。

        用于"名字是程序生成的"场景（开新书自动命名、批量导入）——
        那时候用户没主动取名，不该被重名挡住流程，静默加个序号就行。

        :param base: 基础名（已 strip）
        :return: 可用的名字
        """
        candidate = base
        index = 1
        while await self.name_taken(candidate):
            index += 1
            candidate = f"{base} {index}"
        return candidate

    # ===== 业务方法 =====
    async def create(self, data: NovelCreate) -> Novel:
        """创建作品；名字撞车抛 :class:`NovelNameConflictError`。"""
        self._validate_status(data.status)
        self._validate_outline_mode(data.outline_mode)
        name = data.name.strip()
        if await self.name_taken(name):
            raise NovelNameConflictError(name)
        novel = Novel(**{**data.model_dump(), "name": name})
        self.session.add(novel)
        await self.session.commit()
        await self.session.refresh(novel)
        return novel

    async def get(self, novel_id: int) -> Novel:
        """按 id 查询；不存在抛 NovelNotFoundError。"""
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)
        return novel

    async def list_all(
        self,
        *,
        genre: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Novel]:
        """列出作品，支持按 genre / status 过滤。

        排序：手动顺序（``sort_order``）→ id 升序（同一 sort_order 时保持创建顺序）。

        limit/offset 默认 100/0，phase 1 数据量小够用；
        后续若需要分页/排序，再加 query params。
        """
        if status is not None:
            self._validate_status(status)
        stmt = select(Novel)
        if genre is not None:
            stmt = stmt.where(Novel.genre == genre)
        if status is not None:
            stmt = stmt.where(Novel.status == status)
        stmt = stmt.order_by(Novel.sort_order.asc(), Novel.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, novel_id: int, data: NovelUpdate) -> Novel:
        """部分更新；不存在抛 NovelNotFoundError，改名撞车抛 NovelNameConflictError。"""
        novel = await self.get(novel_id)
        updates = data.model_dump(exclude_unset=True)
        if "status" in updates:
            self._validate_status(updates["status"])
        if "outline_mode" in updates:
            self._validate_outline_mode(updates["outline_mode"])
        if "name" in updates and updates["name"] is not None:
            new_name = updates["name"].strip()
            if not new_name:
                raise NovelValidationError("作品名不能为空")
            if await self.name_taken(new_name, exclude_id=novel_id):
                raise NovelNameConflictError(new_name)
            updates["name"] = new_name
        for key, value in updates.items():
            setattr(novel, key, value)
        await self.session.commit()
        await self.session.refresh(novel)
        return novel

    async def delete(self, novel_id: int) -> None:
        """删除；不存在静默成功（幂等），与 REST DELETE 惯例一致。"""
        novel = await self.session.get(Novel, novel_id)
        if novel is not None:
            await self.session.delete(novel)
            await self.session.commit()

    async def reorder(self, novel_ids: Sequence[int]) -> list[Novel]:
        """按给定顺序重排（``sort_order`` = 下标）。

        :param novel_ids: 用户排好的作品 id 顺序
        :return: 按新顺序排列的作品（不存在的 id 自动跳过）
        """
        unique_ids = list(dict.fromkeys(novel_ids))
        if not unique_ids:
            return []
        result = await self.session.execute(select(Novel).where(Novel.id.in_(unique_ids)))
        rows = {row.id: row for row in result.scalars()}
        ordered: list[Novel] = []
        for index, novel_id in enumerate(unique_ids):
            row = rows.get(novel_id)
            if row is None:
                continue
            row.sort_order = index
            ordered.append(row)

        # ⚠️ 没在列表里的作品必须**推到后面**：它们的 sort_order 会一直是 0，
        #    排序时（sort_order ASC）会跳到最前面，把用户刚排好的顺序搅乱。
        others_stmt = (
            select(Novel)
            .where(Novel.id.notin_(unique_ids))
            .order_by(Novel.sort_order.asc(), Novel.id.asc())
        )
        others = list((await self.session.execute(others_stmt)).scalars())
        offset = len(ordered)
        for i, row in enumerate(others):
            row.sort_order = offset + i

        await self.session.commit()
        return ordered
