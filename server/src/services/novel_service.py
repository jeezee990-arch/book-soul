"""Novel 业务服务（Phase 1.1 作品 CRUD）。

设计：
- Service 不依赖 FastAPI，便于单测和复用
- 所有 DB 操作走 SQLAlchemy 2.x AsyncSession
- 输入校验：status / outline_mode 取值用 models.novel 里的常量
- 错误用领域异常（NotFoundError / ValidationError），由 api 层映射到 HTTP
"""

from __future__ import annotations

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

    # ===== 业务方法 =====
    async def create(self, data: NovelCreate) -> Novel:
        """创建作品。"""
        self._validate_status(data.status)
        self._validate_outline_mode(data.outline_mode)
        novel = Novel(**data.model_dump())
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
        """列出作品，支持按 genre / status 过滤，按 id 升序。

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
        stmt = stmt.order_by(Novel.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, novel_id: int, data: NovelUpdate) -> Novel:
        """部分更新；不存在抛 NovelNotFoundError。"""
        novel = await self.get(novel_id)
        updates = data.model_dump(exclude_unset=True)
        if "status" in updates:
            self._validate_status(updates["status"])
        if "outline_mode" in updates:
            self._validate_outline_mode(updates["outline_mode"])
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
