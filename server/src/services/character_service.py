"""Character 业务服务（Phase 1.2 人物卡 CRUD + 版本化）。

核心流程：
- create：写 Character + 初始 CharacterVersion，关联 current_version_id
- update：部分更新普通字段（如改名字/角色）；不创建新版本（避免噪音）
- update_growth：记录事件；改指定字段；追加 growth_arc；创建新版本
- list_versions / get_version：版本历史查询
- delete：硬删 + 级联删 versions

设计取舍：
- 普通 update 不入版本：版本历史聚焦"性格/状态演化"，避免被 fix typo 刷屏
- growth_arc 自动追加，外部不要直接 set
- is_active 用于软状态（如退场/死亡），不触发版本
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.character import CHARACTER_ROLES, Character, CharacterVersion
from ..models.novel import Novel
from ..schemas.character import (
    CharacterCreate,
    CharacterGrowthUpdate,
    CharacterUpdate,
)


class CharacterServiceError(Exception):
    """Service 层基础异常。"""


class CharacterNotFoundError(CharacterServiceError):
    def __init__(self, character_id: int) -> None:
        super().__init__(f"Character {character_id} not found")
        self.character_id = character_id


class NovelNotFoundError(CharacterServiceError):
    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class CharacterValidationError(CharacterServiceError):
    """字段取值非法。"""


def _utcnow_naive() -> datetime:
    """UTC 当前时间（naive）。"""
    return datetime.now(UTC).replace(tzinfo=None)


class CharacterService:
    """人物卡 CRUD + 版本化服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_role(role: str | None) -> None:
        if role is not None and role not in CHARACTER_ROLES:
            raise CharacterValidationError(f"Invalid role: {role!r}; allowed: {CHARACTER_ROLES}")

    async def _ensure_novel_exists(self, novel_id: int) -> None:
        novel = await self.session.get(Novel, novel_id)
        if novel is None:
            raise NovelNotFoundError(novel_id)

    # ===== 业务方法 =====
    async def create(self, data: CharacterCreate) -> Character:
        """创建人物卡 + 初始版本。"""
        self._validate_role(data.role)
        await self._ensure_novel_exists(data.novel_id)

        # 1) 建 character（不含 current_version_id，flush 后再回填）
        char_data = data.model_dump()
        is_active = char_data.pop("is_active", True)
        character = Character(**char_data, is_active=is_active)
        self.session.add(character)
        await self.session.flush()  # 让 character.id 可用

        # 2) 建初始版本
        snapshot = data.model_dump()
        version = CharacterVersion(
            character_id=character.id,
            parent_version_id=None,
            snapshot=snapshot,
            change_reason="initial",
            trigger_event=None,
        )
        self.session.add(version)
        await self.session.flush()

        # 3) 回填 current_version_id
        character.current_version_id = version.id
        await self.session.commit()
        await self.session.refresh(character)
        return character

    async def get(self, character_id: int) -> Character:
        """按 id 查询；不存在抛 CharacterNotFoundError。"""
        character = await self.session.get(Character, character_id)
        if character is None:
            raise CharacterNotFoundError(character_id)
        return character

    async def list_all(
        self,
        novel_id: int | None = None,
        *,
        role: str | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Character]:
        """列出人物卡，支持 novel_id / role / is_active 过滤。

        ``novel_id`` 是位置参数（最常用），其它按 kwarg。
        """
        self._validate_role(role)
        stmt = select(Character)
        if novel_id is not None:
            stmt = stmt.where(Character.novel_id == novel_id)
        if role is not None:
            stmt = stmt.where(Character.role == role)
        if is_active is not None:
            stmt = stmt.where(Character.is_active == is_active)
        stmt = stmt.order_by(Character.id.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_active_characters(self, novel_id: int) -> list[Character]:
        """获取某作品所有活跃人物（创作时使用）。"""
        return await self.list_all(novel_id=novel_id, is_active=True)

    async def update(self, character_id: int, data: CharacterUpdate) -> Character:
        """部分更新普通字段。不创建新版本。"""
        character = await self.get(character_id)
        updates = data.model_dump(exclude_unset=True)
        if "role" in updates:
            self._validate_role(updates["role"])
        for key, value in updates.items():
            setattr(character, key, value)
        await self.session.commit()
        await self.session.refresh(character)
        return character

    async def update_growth(
        self, character_id: int, data: CharacterGrowthUpdate
    ) -> CharacterVersion:
        """记录一次性格/状态变化事件。

        行为：
        - 追加 ``[<date>] <event>`` 到 growth_arc
        - 把 ``new_*`` 字段写回 character
        - 创建新版本，parent_version_id 指向当前版本
        """
        character = await self.get(character_id)

        # 1) 写回指定字段
        if data.new_personality is not None:
            character.personality = data.new_personality
        if data.new_habits is not None:
            character.habits = data.new_habits
        if data.new_thinking is not None:
            character.thinking = data.new_thinking
        if data.new_relationships is not None:
            character.relationships = data.new_relationships

        # 2) 追加 growth_arc
        growth_line = f"[{_utcnow_naive().strftime('%Y-%m-%d')}] {data.event}"
        if character.growth_arc:
            character.growth_arc = character.growth_arc + "\n" + growth_line
        else:
            character.growth_arc = growth_line

        # 3) 快照（只存本次变化的字段，避免膨胀）
        snapshot: dict[str, str] = {
            "event": data.event,
        }
        if data.new_personality is not None:
            snapshot["personality"] = data.new_personality
        if data.new_habits is not None:
            snapshot["habits"] = data.new_habits
        if data.new_thinking is not None:
            snapshot["thinking"] = data.new_thinking
        if data.new_relationships is not None:
            snapshot["relationships"] = data.new_relationships
        snapshot["growth_arc"] = character.growth_arc

        # 4) 新版本
        new_version = CharacterVersion(
            character_id=character.id,
            parent_version_id=character.current_version_id,
            snapshot=snapshot,
            change_reason="event_trigger",
            trigger_event=data.event,
        )
        self.session.add(new_version)
        await self.session.flush()

        # 5) 更新 current_version_id
        character.current_version_id = new_version.id
        await self.session.commit()
        await self.session.refresh(new_version)
        return new_version

    async def delete(self, character_id: int) -> None:
        """删除（硬删 + 级联删 versions）。幂等。"""
        character = await self.session.get(Character, character_id)
        if character is not None:
            await self.session.delete(character)
            await self.session.commit()

    # ===== 版本历史 =====
    async def list_versions(self, character_id: int) -> list[CharacterVersion]:
        """查看人物卡版本历史（按 created_at 倒序）。"""
        # 先确保人物存在，不存在抛 CharacterNotFoundError
        await self.get(character_id)
        stmt = (
            select(CharacterVersion)
            .where(CharacterVersion.character_id == character_id)
            .order_by(CharacterVersion.created_at.desc(), CharacterVersion.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def get_version(self, character_id: int, version_id: int) -> CharacterVersion:
        """获取指定版本；不存在或不属于该 character 抛 NotFound。"""
        # 1) 确保 character 存在
        await self.get(character_id)
        # 2) 取版本并校验所属
        version = await self.session.get(CharacterVersion, version_id)
        if version is None or version.character_id != character_id:
            raise CharacterNotFoundError(character_id)  # 复用：标识"找不到该 character 下的版本"
        return version
