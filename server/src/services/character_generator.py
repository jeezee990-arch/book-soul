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
    strip_thinking,
)
from ..core.paths import prompts_dir
from ..core.skills import manager as skill_manager
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


class _CardQueueHandle:
    """单张卡的流式句柄：内部 queue + producer task + name。

    用于 ``stream_generate_from_outline`` 协调多张卡并行生成。
    """

    __slots__ = ("name", "q", "task")

    def __init__(self, name: str, q: asyncio.Queue, task: asyncio.Task) -> None:
        self.name = name
        self.q = q
        self.task = task


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

        # 2) Step 1：抽取人物列表
        extracted = await self._extract_characters(outline)

        if not extracted:
            return {
                "novel_id": novel_id,
                "characters": [],
                "provider": self._llm_provider_name(),
                "model": self._llm_model_name(),
            }

        # 3) Step 2：并行生成每张卡
        llm = self._llm
        owns_client = self._llm_override is None and llm is not None
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
            if owns_client and llm is not None:
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
    async def _extract_characters(self, outline: dict) -> list[dict[str, str]]:
        """调 LLM 抽取人物列表；返回 ``[{"name": ..., "role": ...}, ...]``。"""
        template = _load_prompt("extract_characters")
        outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        prompt = template.format(outline=outline_str)

        llm = self._llm
        owns_client = self._llm_override is None
        if llm is None:
            llm = self._get_llm()
            owns_client = True
        try:
            resp = await llm.chat([ChatMessage("user", prompt)], temperature=0.5)
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed (extract): {}", describe_llm_error(e))
            raise CharacterGenerationError(describe_llm_error(e)) from e
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

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

        协议：
        - ``{"event": "phase", "phase": "extract"}``
        - ``{"event": "extract_delta", "text": "..."}``
        - ``{"event": "extract_done", "characters": [{"name":..., "role":...}, ...]}``
        - ``{"event": "card_start", "name": "...", "role": "..."}``
        - ``{"event": "card_delta", "name": "...", "text": "..."}``
        - ``{"event": "card_done", "name": "...", "id": <int>}``
        - ``{"event": "done", "saved_count": n, "provider": "...", "model": "..."}``
        - ``{"event": "error", "message": "..."}``
        """
        if not isinstance(outline, dict):
            yield {"event": "error", "message": "outline must be dict"}
            return
        if not genre:
            yield {"event": "error", "message": "genre must be non-empty"}
            return

        char_service = CharacterService(self.session)
        try:
            await char_service._ensure_novel_exists(novel_id)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "message": f"novel not found: {e}"}
            return

        # 流式版：使用缓存单例（不释放 → httpx 连接复用）
        if self._llm_override is not None:
            llm = self._llm_override
            owns_client = True
        else:
            from ..core.llm import get_cached_llm_client

            llm = get_cached_llm_client("character_generation")
            self._llm = llm
            owns_client = False
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")

        yield {"event": "phase", "phase": "extract"}

        # Step 1: 流式抽取人物
        extracted: list[dict[str, str]] = []
        try:
            template = _load_prompt("extract_characters")
            outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
            extra_block = ""
            if user_extra.strip():
                extra_block = f"\n\n【作者个人想法（请在生成时参考）】\n{user_extra.strip()}\n"
            extract_prompt = template.format(outline=outline_str) + extra_block
            full_text = ""
            stream = await llm.chat(
                [ChatMessage("user", extract_prompt)],
                temperature=0.5,
                stream=True,
            )
            async for delta in stream:  # type: ignore[union-attr]
                if not delta:
                    continue
                if "<think>" in delta and "</think>" not in delta:
                    continue
                full_text += delta
                yield {"event": "extract_delta", "text": delta}
            cleaned = strip_thinking(full_text)
            if cleaned:
                arr = extract_json_array(cleaned)
                for item in arr:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "")).strip()
                    if not name:
                        continue
                    role = _normalize_role(str(item.get("role", "其他")))
                    extracted.append({"name": name, "role": role})
        except CharacterGenerationError as e:
            yield {"event": "error", "message": str(e)}
            if owns_client:
                await self._release_llm(llm, owns=True)
            return
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "message": describe_llm_error(e)}
            if owns_client:
                await self._release_llm(llm, owns=True)
            return

        if not extracted:
            yield {"event": "done", "saved_count": 0, "provider": provider, "model": model}
            if owns_client:
                await self._release_llm(llm, owns=True)
            return

        yield {"event": "extract_done", "characters": extracted}

        # Step 2: 并行流式生成每张卡；每个 card 用 queue 透出事件
        yield {"event": "phase", "phase": "cards"}

        async def card_runner(item: dict[str, str]) -> _CardQueueHandle:
            """单卡流式生成 → 解析 → 入库。"""
            q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

            async def produce() -> None:
                try:
                    await q.put({"event": "card_start", "name": item["name"], "role": item["role"]})
                    full_text = ""
                    stream = await llm.chat(
                        [
                            ChatMessage(
                                "user",
                                self._build_card_prompt(
                                    name=item["name"],
                                    role=item["role"],
                                    genre=genre,
                                    outline=outline,
                                    user_extra=user_extra,
                                ),
                            )
                        ],
                        temperature=0.7,
                        stream=True,
                    )
                    async for delta in stream:  # type: ignore[union-attr]
                        if not delta:
                            continue
                        if "<think>" in delta and "</think>" not in delta:
                            continue
                        full_text += delta
                        await q.put(
                            {
                                "event": "card_delta",
                                "name": item["name"],
                                "text": delta,
                            }
                        )
                    # 解析 + 入库
                    cleaned = strip_thinking(full_text)
                    # 自动调用 scene=character_generation 的 post-process skills
                    post_cleaned = await skill_manager.apply_post("character_generation", cleaned)
                    data = extract_yaml_block(post_cleaned)
                    card = {
                        "name": item["name"],
                        "role": item["role"],
                        "basic_info": _trim_to_str(data.get("basic_info")),
                        "personality": _trim_to_str(data.get("personality")),
                        "habits": _trim_to_str(data.get("habits")),
                        "thinking": _trim_to_str(data.get("thinking")),
                        "relationships": _trim_to_str(data.get("relationships")),
                        "growth_arc": _trim_to_str(data.get("growth_arc")),
                    }
                    from ..schemas.character import CharacterCreate

                    character = await char_service.create(
                        CharacterCreate(novel_id=novel_id, **card)
                    )
                    await q.put(
                        {
                            "event": "card_done",
                            "name": item["name"],
                            "id": character.id,
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("card {} failed: {}", item["name"], describe_llm_error(e))
                    await q.put(
                        {
                            "event": "error",
                            "message": f"card {item['name']}: {describe_llm_error(e)}",
                        }
                    )
                finally:
                    await q.put(None)

            task = asyncio.create_task(produce())
            return _CardQueueHandle(name=item["name"], q=q, task=task)

        handles = [await card_runner(item) for item in extracted]
        try:
            finished = 0
            while finished < len(handles):
                get_tasks = [asyncio.create_task(h.q.get()) for h in handles]
                done, _ = await asyncio.wait(get_tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    payload = t.result()
                    if payload is None:
                        finished += 1
                    else:
                        yield payload
                    for pending in _:
                        pending.cancel()
        finally:
            await asyncio.gather(*(h.task for h in handles), return_exceptions=True)
            if owns_client:
                await self._release_llm(llm, owns=True)

        yield {
            "event": "done",
            "saved_count": len(extracted),
            "provider": provider,
            "model": model,
        }

    def _build_card_prompt(
        self,
        *,
        name: str,
        role: str,
        genre: str,
        outline: dict,
        user_extra: str = "",
    ) -> str:
        """构造单卡 prompt（含 user_extra）。"""
        template = _load_prompt("generate_card")
        outline_ctx = json.dumps(outline, ensure_ascii=False)
        if len(outline_ctx) > 2000:
            outline_ctx = outline_ctx[:2000] + "\n... (truncated)"
        prompt = template.format(name=name, role=role, genre=genre, outline_context=outline_ctx)
        if user_extra.strip():
            prompt += f"\n\n【作者个人想法（参考即可）】\n{user_extra.strip()}\n"
        return prompt


__all__ = [
    "CharacterGenerator",
    "CharacterGenerationError",
]
