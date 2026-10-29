"""人物卡自动生成（Phase 3.5）。

设计：
- 加载 ``config/prompts/character_generation.yaml`` 模板（lru_cache）
- 两阶段 LLM 调用：
  1) extract_characters：从大纲抽取人物列表（JSON 数组）
  2) generate_card：为每个人物生成完整卡（YAML 块）
- 解析：strip thinking + extract_json_array / extract_yaml_block
- 入库：复用 CharacterService.create（自动建初始版本）
- 失败 → :class:`CharacterGenerationError`

不做的事：
- 不修改 character_service.py（保持该文件行数稳定）
- 不做人物关系图谱（Phase 4+ 考虑）
- 不做批量重生成 UI（前端可按 character_id 单独 PATCH）
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import yaml
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.formatting import (
    extract_json_array,
    extract_yaml_block,
)
from ..core.paths import prompts_dir
from ._character_helpers import (
    CharacterGenerationError,
    _LLMClientLike,
    _normalize_role,
    _trim_to_str,
)
from .character_service import CharacterService

_PROMPTS_DIR = prompts_dir()


@lru_cache(maxsize=4)
def _load_prompt(section: str) -> str:
    """加载 ``character_generation.yaml`` 中指定 section 的 prompt。

    缓存到 lru_cache；测试可用 ``_load_prompt.cache_clear()`` 清除。
    """
    path = _PROMPTS_DIR / "character_generation.yaml"
    if not path.is_file():
        raise CharacterGenerationError(f"Prompt file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or section not in data:
        raise CharacterGenerationError(f"Prompt file {path} missing section {section!r}")
    return str(data[section])


class CharacterGenerator:
    """人物卡自动生成服务（Phase 3.5）。

    职责：
    - 两阶段 LLM 调用（提取列表 + 生成卡）
    - YAML 解析 + 字段映射到 CharacterCreate
    - 复用 CharacterService.create 入库
    - 失败抛 :class:`CharacterGenerationError`
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_client: _LLMClientLike | None = None,
    ) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    # ===== 给流式模块用的公开访问口 =====
    #
    # 流式实现拆到了 :mod:`src.services.character_stream`（避免本文件超 500 行），
    # 那边通过这几个属性访问本对象 —— 用公开属性而不是 ``_`` 私有字段，
    # 是为了让"拆出去"这件事在类型层面就说得清楚。

    @property
    def llm(self) -> _LLMClientLike | None:
        """当前 LLM 客户端（可能是 None）。"""
        return self._llm

    @llm.setter
    def llm(self, value: _LLMClientLike | None) -> None:
        """设置当前 LLM 客户端（流式路径用缓存单例时回填）。"""
        self._llm = value

    @property
    def llm_override(self) -> _LLMClientLike | None:
        """外部注入的客户端（测试用 mock；None = 用缓存单例）。"""
        return self._llm_override

    @staticmethod
    def load_prompt(section: str) -> str:
        """加载人物卡 prompt 模板（供流式模块复用同一份缓存）。"""
        return _load_prompt(section)

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("character_generation")
        return self._llm

    async def _release_llm(self, llm: _LLMClientLike, owns: bool) -> None:
        """懒加载的客户端用完关闭（防连接泄漏），并清缓存让下次重建。"""
        aclose = getattr(llm, "aclose", None)
        if owns and aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    async def release_llm(self, llm: _LLMClientLike, owns: bool) -> None:
        """释放 LLM 客户端（流式模块用的公开入口）。"""
        await self._release_llm(llm, owns)

    # ===== 主入口 =====
    async def generate_from_outline(
        self,
        novel_id: int,
        outline: dict,
        *,
        genre: str = "通用",
    ) -> dict:
        """从大纲生成人物卡列表并入库。

        :raises CharacterGenerationError: 任何一步失败（novel 不存在会改抛 NovelNotFoundError）
        :raises NovelNotFoundError: novel_id 不存在
        """
        if not isinstance(outline, dict):
            raise CharacterGenerationError(f"outline must be dict, got {type(outline).__name__}")
        if not genre or not isinstance(genre, str):
            raise CharacterGenerationError("genre must be non-empty str")

        # 1) 校验 novel 存在
        char_service = CharacterService(self.session)
        await char_service._ensure_novel_exists(novel_id)  # noqa: SLF001

        # 2) 取一次 LLM 客户端，抽取和生成卡**共用**它，最后统一释放。
        #
        # ⚠️ 2026-10-29 巡检抓到的真 bug：
        #    旧代码里 ``_extract_characters`` 自己取客户端、用完在 finally 里
        #    释放（``self._llm`` 置 None），而 Step 2 紧接着读 ``self._llm`` ——
        #    生产路径（没有注入 mock 客户端）拿到的是 **None** →
        #    ``None.chat(...)`` → AttributeError → 整条人物卡生成失败。
        #    测试之所以没发现：所有用例都注入了 ``llm_client=mock``，
        #    ``self._llm`` 一直是那个 mock，释放逻辑不会把它置空。
        llm = self._llm if self._llm is not None else self._get_llm()
        owns_client = self._llm_override is None
        try:
            # 3) Step 1：抽取人物列表
            extracted = await self._extract_characters(outline, llm)

            if not extracted:
                return {
                    "novel_id": novel_id,
                    "characters": [],
                    "provider": self._llm_provider_name(),
                    "model": self._llm_model_name(),
                }

            # 4) Step 2：并行生成每张卡
            try:
                cards = await asyncio.gather(
                    *(
                        self._generate_one_card(
                            llm,
                            name=item["name"],
                            role=item["role"],
                            genre=genre,
                            outline=outline,
                        )
                        for item in extracted
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.error("LLM call failed (character): {}", describe_llm_error(e))
                raise CharacterGenerationError(describe_llm_error(e)) from e
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

        # 4) 入库（每张卡用 CharacterService.create，自动建初始版本）
        from ..schemas.character import CharacterCreate

        saved: list = []
        for card in cards:
            try:
                payload = CharacterCreate(
                    novel_id=novel_id,
                    name=card["name"],
                    role=card["role"],
                    basic_info=card.get("basic_info"),
                    personality=card.get("personality"),
                    habits=card.get("habits"),
                    thinking=card.get("thinking"),
                    relationships=card.get("relationships"),
                    growth_arc=card.get("growth_arc"),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Skip invalid card {}: {}", card.get("name"), e)
                continue
            character = await char_service.create(payload)
            saved.append(character)

        return {
            "novel_id": novel_id,
            "characters": saved,
            "provider": self._llm_provider_name(),
            "model": self._llm_model_name(),
        }

    # ===== 内部：Step 1 抽取 =====
    async def _extract_characters(self, outline: dict, llm: _LLMClientLike) -> list[dict[str, str]]:
        """调 LLM 抽取人物列表；返回 ``[{"name": ..., "role": ...}, ...]``。

        ⚠️ 客户端由调用方持有（:meth:`generate_from_outline` 统一取一次、统一释放）。
        以前这里自己取自己放，抽取完把 ``self._llm`` 置成 None，
        导致后面生成卡那一步拿到 None（生产路径必炸 —— 见上面的注释）。
        """
        template = _load_prompt("extract_characters")
        outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        prompt = template.format(outline=outline_str)

        try:
            resp = await llm.chat([ChatMessage("user", prompt)], temperature=0.5)
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed (extract): {}", describe_llm_error(e))
            raise CharacterGenerationError(describe_llm_error(e)) from e

        raw = resp.content if isinstance(resp.content, str) else ""
        if not raw.strip():
            raise CharacterGenerationError("LLM returned empty content (extract)")
        try:
            arr = extract_json_array(raw)
        except ValueError as e:
            raise CharacterGenerationError(str(e)) from e

        # 标准化：每项必须含 name + role；role 不合法 → 归到"其他"
        normalized: list[dict[str, str]] = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            role = _normalize_role(str(item.get("role", "其他")))
            normalized.append({"name": name, "role": role})
        return normalized

    # ===== 内部：Step 2 生成单卡 =====
    async def _generate_one_card(
        self,
        llm: _LLMClientLike,
        *,
        name: str,
        role: str,
        genre: str,
        outline: dict,
    ) -> dict:
        """调 LLM 为单个人物生成完整卡；返回字段 dict。"""
        template = _load_prompt("generate_card")
        outline_ctx = json.dumps(outline, ensure_ascii=False)
        # 截断过长大纲（防止 prompt 超长）；保留头 2000 字符
        if len(outline_ctx) > 2000:
            outline_ctx = outline_ctx[:2000] + "\n... (truncated)"
        prompt = template.format(name=name, role=role, genre=genre, outline_context=outline_ctx)
        resp = await llm.chat([ChatMessage("user", prompt)], temperature=0.7)
        raw = resp.content if isinstance(resp.content, str) else ""
        if not raw.strip():
            raise CharacterGenerationError(f"LLM returned empty content (card: {name})")
        try:
            data = extract_yaml_block(raw)
        except ValueError as e:
            raise CharacterGenerationError(f"card {name}: {e}") from e

        return {
            "name": name,
            "role": role,
            "basic_info": _trim_to_str(data.get("basic_info")),
            "personality": _trim_to_str(data.get("personality")),
            "habits": _trim_to_str(data.get("habits")),
            "thinking": _trim_to_str(data.get("thinking")),
            "relationships": _trim_to_str(data.get("relationships")),
            "growth_arc": _trim_to_str(data.get("growth_arc")),
        }

    # ===== LLM 元信息 =====
    def _llm_provider_name(self) -> str:
        llm = self._llm or self._llm_override
        return str(getattr(llm, "provider", "unknown") or "unknown")

    def _llm_model_name(self) -> str:
        llm = self._llm or self._llm_override
        return str(getattr(llm, "model", "") or "")

    @staticmethod
    def clear_prompt_cache() -> None:
        """测试用：清 prompt lru_cache。"""
        _load_prompt.cache_clear()

    # ===== 流式（Phase 性能优化）=====

    async def stream_generate_from_outline(
        self,
        novel_id: int,
        outline: dict,
        *,
        genre: str = "通用",
        user_extra: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """流式生成人物卡（边抽取边推 + 每张卡实时生成 + 入库）。

        实现拆在 :mod:src.services.character_stream（避免本文件超 500 行），
        这里只做一层薄封装，协议见那个模块的 docstring。
        """
        from .character_stream import stream_generate_from_outline

        async for event in stream_generate_from_outline(
            self,
            novel_id,
            outline,
            genre=genre,
            user_extra=user_extra,
        ):
            yield event


__all__ = [
    "CharacterGenerator",
    "CharacterGenerationError",
]
