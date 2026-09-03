"""Chapter 业务服务（Phase 1.3 章节 CRUD + 版本基础）。

核心流程：
- create：建 chapter；如果带 content，再写一条 user_create 版本
- update：部分更新元数据（title/outline/chapter_number/status），不入版本
- update_content：写一条新版本（user_edit / rewrite / llm_generate）
- list_versions / get_version：版本历史
- delete：硬删 + 级联删 versions

字数：v1 用 len(content) 简单实现（v2 可换中文分词）
chapter_number 不强制唯一：service 层校验"作品内不重复"
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter import CHAPTER_STATUSES, VERSION_TRIGGERS, Chapter, ChapterVersion
from ..models.novel import Novel
from ..schemas.chapter import (
    ChapterContentUpdate,
    ChapterCreate,
    ChapterUpdate,
)


def _word_count(content: str) -> int:
    """v1 简单字数 = len(content)；后续可换中文分词。"""
    return len(content)


class ChapterServiceError(Exception):
    """Service 层基础异常。"""


class ChapterNotFoundError(ChapterServiceError):
    def __init__(self, chapter_id: int) -> None:
        super().__init__(f"Chapter {chapter_id} not found")
        self.chapter_id = chapter_id


class NovelNotFoundError(ChapterServiceError):
    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class ChapterValidationError(ChapterServiceError):
    """字段取值非法。"""


class ChapterNumberConflictError(ChapterServiceError):
    """作品内 chapter_number 已存在。"""

    def __init__(self, novel_id: int, chapter_number: int) -> None:
        super().__init__(f"Chapter number {chapter_number} already exists in novel {novel_id}")
        self.novel_id = novel_id
        self.chapter_number = chapter_number


class ChapterService:
    """章节 CRUD + 版本化服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_status(status: str | None) -> None:
        if status is not None and status not in CHAPTER_STATUSES:
            raise ChapterValidationError(f"Invalid status: {status!r}; allowed: {CHAPTER_STATUSES}")

    @staticmethod
    def _validate_trigger(trigger: str) -> None:
        if trigger not in VERSION_TRIGGERS:
            raise ChapterValidationError(
                f"Invalid trigger: {trigger!r}; allowed: {VERSION_TRIGGERS}"
            )

    async def _ensure_novel_exists(self, novel_id: int) -> None:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)

    async def _check_chapter_number_unique(self, novel_id: int, chapter_number: int) -> None:
        """作品内 chapter_number 不应重复。"""
        stmt = (
            select(Chapter)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise ChapterNumberConflictError(novel_id, chapter_number)

    # ===== 业务方法 =====
    async def create(self, data: ChapterCreate) -> Chapter:
        """创建章节；带 content 则写初始版本。"""
        self._validate_status(data.status)
        await self._ensure_novel_exists(data.novel_id)
        await self._check_chapter_number_unique(data.novel_id, data.chapter_number)

        chapter = Chapter(
            novel_id=data.novel_id,
            chapter_number=data.chapter_number,
            title=data.title,
            outline=data.outline,
            status=data.status,
            word_count=0,
        )
        self.session.add(chapter)
        await self.session.flush()  # 让 chapter.id 可用

        if data.content:
            wc = _word_count(data.content)
            version = ChapterVersion(
                chapter_id=chapter.id,
                parent_version_id=None,
                content=data.content,
                trigger="user_create",
                prompt=None,
                metadata_=None,
                word_count=wc,
            )
            self.session.add(version)
            await self.session.flush()
            chapter.current_version_id = version.id
            chapter.word_count = wc
            # 用户没显式指定 status 时，建带内容的章节自动从 outline → drafting
            if chapter.status == "outline":
                chapter.status = "drafting"

        await self.session.commit()
        await self.session.refresh(chapter)
        return chapter

    async def get(self, chapter_id: int) -> Chapter:
        """按 id 查询；不存在抛 NotFound。"""
        chapter = await self.session.get(Chapter, chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(chapter_id)
        return chapter

    async def list_all(
        self,
        novel_id: int | None = None,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Chapter]:
        """列出章节，支持 novel_id / status 过滤，按 chapter_number 升序。"""
        self._validate_status(status)
        stmt = select(Chapter)
        if novel_id is not None:
            stmt = stmt.where(Chapter.novel_id == novel_id)
        if status is not None:
            stmt = stmt.where(Chapter.status == status)
        stmt = (
            stmt.order_by(Chapter.chapter_number.asc(), Chapter.id.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, chapter_id: int, data: ChapterUpdate) -> Chapter:
        """部分更新元数据。改 chapter_number 时校验唯一性。"""
        chapter = await self.get(chapter_id)
        updates = data.model_dump(exclude_unset=True)
        if "status" in updates:
            self._validate_status(updates["status"])
        if "chapter_number" in updates and updates["chapter_number"] != chapter.chapter_number:
            await self._check_chapter_number_unique(chapter.novel_id, updates["chapter_number"])
        for key, value in updates.items():
            setattr(chapter, key, value)
        await self.session.commit()
        await self.session.refresh(chapter)
        return chapter

    async def update_content(self, chapter_id: int, data: ChapterContentUpdate) -> ChapterVersion:
        """写新版本（正文更新）。"""
        self._validate_trigger(data.trigger)
        chapter = await self.get(chapter_id)
        wc = _word_count(data.content)
        version = ChapterVersion(
            chapter_id=chapter.id,
            parent_version_id=chapter.current_version_id,
            content=data.content,
            diff=None,  # diff 计算留给 Phase 4
            trigger=data.trigger,
            prompt=data.prompt,
            metadata_=data.metadata,
            word_count=wc,
        )
        self.session.add(version)
        await self.session.flush()
        chapter.current_version_id = version.id
        chapter.word_count = wc
        # 写完内容自动推到 "drafting"（除非已经是 written/final）
        if chapter.status == "outline":
            chapter.status = "drafting"
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def delete(self, chapter_id: int) -> None:
        """硬删 + 级联删 versions。幂等。"""
        chapter = await self.session.get(Chapter, chapter_id)
        if chapter is not None:
            await self.session.delete(chapter)
            await self.session.commit()

    # ===== 版本历史 =====
    async def list_versions(self, chapter_id: int) -> list[ChapterVersion]:
        """按 created_at 倒序。"""
        await self.get(chapter_id)  # 校验存在
        stmt = (
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.created_at.desc(), ChapterVersion.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_version(self, chapter_id: int, version_id: int) -> ChapterVersion:
        """获取单个版本；不属于该 chapter 抛 NotFound。"""
        await self.get(chapter_id)
        version = await self.session.get(ChapterVersion, version_id)
        if version is None or version.chapter_id != chapter_id:
            raise ChapterNotFoundError(chapter_id)
        return version
