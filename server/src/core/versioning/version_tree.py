"""版本树管理（Phase 4.6）。

职责：
- 在已有 :class:`~src.models.chapter.ChapterVersion` 之上提供"树形"操作
  （列出版本 / 计算与上一版 diff / 软回滚）
- 不直接修改 chapter_service 的 update_content，保持职责单一
  （``update_content`` 内部已可自动计算 diff；本模块供"回滚 / 跨版本 diff"用）

回滚语义（参考 PROJECT_PLAN.md v1.2 §4.6）：
- 软回滚：把目标版本的内容设为当前内容，生成新版本（parent = 当前最新）
- 触发 trigger="rollback"；prompt="rollback_to:{version_id}"
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.chapter import Chapter, ChapterVersion
from ...schemas.chapter import ChapterContentUpdate
from ...services.chapter_service import ChapterService
from .diff import compute_unified_diff


class VersionTreeError(Exception):
    """版本树操作失败。"""


class VersionNotFoundError(VersionTreeError):
    def __init__(self, version_id: int) -> None:
        super().__init__(f"Version {version_id} not found")
        self.version_id = version_id


class VersionTree:
    """章节的版本树视图。

    使用：
        tree = VersionTree(session, chapter_id=42)
        await tree.save_version(content, trigger="user_edit")
        versions = await tree.list_versions()
        diff = await tree.diff_with_parent(version_id=5)
    """

    def __init__(self, session: AsyncSession, *, chapter_id: int) -> None:
        self.session = session
        self.chapter_id = chapter_id
        self._chapter_svc = ChapterService(session)

    async def _ensure_chapter(self) -> Chapter:
        return await self._chapter_svc.get(self.chapter_id)

    async def save_version(
        self,
        content: str,
        *,
        trigger: str,
        parent_id: int | None = None,
        prompt: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChapterVersion:
        """写一条新版本，并计算与 parent 的 unified diff。

        :param parent_id: 显式指定 parent；None = 用 chapter.current_version_id
        """
        await self._ensure_chapter()
        # 决定 parent
        if parent_id is None:
            chapter = await self.session.get(Chapter, self.chapter_id)
            assert chapter is not None  # _ensure_chapter 已校验
            parent_id = chapter.current_version_id

        # 算 diff
        parent_content: str | None = None
        if parent_id is not None:
            parent = await self.session.get(ChapterVersion, parent_id)
            if parent is not None and parent.chapter_id == self.chapter_id:
                parent_content = parent.content
        diff = compute_unified_diff(
            parent_content, content, fromfile=f"v{parent_id or 0}", tofile="new"
        )

        payload = ChapterContentUpdate(
            content=content,
            trigger=trigger,
            prompt=prompt,
            metadata={**(metadata or {}), "diff_size": len(diff)} if diff else metadata,
        )
        return await self._chapter_svc.update_content(self.chapter_id, payload)

    async def list_versions(self) -> list[ChapterVersion]:
        """列出该 chapter 的所有版本（按时间倒序）。"""
        await self._ensure_chapter()
        stmt = (
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == self.chapter_id)
            .order_by(ChapterVersion.created_at.desc(), ChapterVersion.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def diff_with_parent(self, version_id: int) -> str:
        """拿版本 version_id 与其 parent 之间的 unified diff（无 parent → 返回空）。"""
        version = await self.session.get(ChapterVersion, version_id)
        if version is None or version.chapter_id != self.chapter_id:
            raise VersionNotFoundError(version_id)
        if version.parent_version_id is None:
            return ""
        parent = await self.session.get(ChapterVersion, version.parent_version_id)
        if parent is None:
            return ""
        return compute_unified_diff(
            parent.content,
            version.content,
            fromfile=f"v{parent.id}",
            tofile=f"v{version.id}",
        )

    async def diff_between(self, old_id: int, new_id: int) -> str:
        """两个版本间的 diff（任意方向，old → new）。"""
        old = await self.session.get(ChapterVersion, old_id)
        new = await self.session.get(ChapterVersion, new_id)
        if old is None or old.chapter_id != self.chapter_id:
            raise VersionNotFoundError(old_id)
        if new is None or new.chapter_id != self.chapter_id:
            raise VersionNotFoundError(new_id)
        return compute_unified_diff(
            old.content, new.content, fromfile=f"v{old.id}", tofile=f"v{new.id}"
        )

    async def rollback(self, version_id: int) -> ChapterVersion:
        """软回滚：把目标版本内容设为当前内容，生成新版本（parent=当前最新）。

        - 触发 trigger="rollback"
        - prompt="rollback_to:{version_id}"
        - metadata 含原版本的 trigger / created_at（方便审计）
        """
        target = await self.session.get(ChapterVersion, version_id)
        if target is None or target.chapter_id != self.chapter_id:
            raise VersionNotFoundError(version_id)

        chapter = await self.session.get(Chapter, self.chapter_id)
        assert chapter is not None  # _ensure_chapter 已校验
        latest_id = chapter.current_version_id

        if latest_id == version_id:
            logger.info(
                "rollback noop: target == current (chapter={}, v={})", self.chapter_id, version_id
            )
            return target

        rollback_meta = {
            "rollback_from_version": version_id,
            "rollback_at": datetime.now(UTC).isoformat(),
            "original_trigger": target.trigger,
        }
        return await self.save_version(
            content=target.content,
            trigger="rollback",
            parent_id=latest_id,
            prompt=f"rollback_to:{version_id}",
            metadata=rollback_meta,
        )


__all__ = [
    "VersionTree",
    "VersionTreeError",
    "VersionNotFoundError",
]
