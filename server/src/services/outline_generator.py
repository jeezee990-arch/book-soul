"""基于剧情生成大纲（Phase 3.4；2026-10-25 起改为**两阶段**）。

三种模式
--------
- ``complete``：完整大纲，从开头写到全书结束（适合短篇小说）
- ``semi_open``：半开放式，只写前期并留悬念，后续由作者自行创作或 AI 辅助续写
- ``freedom``：创作型，散文 + 关键节拍 + 主题

两条生成路径
------------
=========  ==========================================  ==========================
模式        路径                                     耗时特征
=========  ==========================================  ==========================
complete    两阶段（骨架 → 各卷**并行**补细节）        快：总耗时 ≈ 最慢的那一卷
semi_open   同上（额外产出 suspense_hook）           快
freedom     单阶段（一次调用出完整结构）              它本来就不是"卷 → 章"结构
=========  ==========================================  ==========================

两阶段的意义（2026-10-25 实测）
-------------------------------
旧实现一次调用要吐 1.2 万 token，30 章的大纲花了 **300 秒**（思考 135s + 输出 165s），
而且 prompt 里把规模写死成"20-40 章"，作者写的"100 章"被无视。

现在：
- **规模显式参数化**（见 :mod:`src.core.outline_scale`）→ 作者的要求能生效
- **两阶段 + 并行** → 用户几十秒看到全书骨架，细节并行补齐

流式协议
--------
- ``{"event": "start", "phase": "outline", "total_chapters": N, "volume_count": M, ...}``
- ``{"event": "thinking", "text": "..."}``（模型思考中；带 ``index`` 的是某卷的思考）
- ``{"event": "partial", "structure": {...}, "chapters_done": N}``（结构化增量）
- ``{"event": "skeleton", "structure": {...}, "chapters_done": N}``（骨架完成）
- ``{"event": "volume_start" / "volume_done" / "volume_error", "index": i, ...}``
- ``{"event": "done", "novel_id": ..., "outline_id": ..., "structure": ..., "elapsed_sec": ..., "first_delta_sec": ...}``
- ``{"event": "error", "message": "..."}``

⚠️ **不再推 ``delta`` 事件**：旧协议把 LLM 吐的原始 JSON 逐字推给前端用 ``<pre>``
渲染 —— 用户看到的是一堆英文代码。现在推**已经解析好的结构**。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.outline_scale import normalize_scale
from ..core.paths import prompts_dir
from ..core.skills import manager as skill_manager
from ..models.novel import Novel
from ..models.outline import OUTLINE_TYPES
from .outline_errors import OutlineGenerationError
from .outline_service import OutlineService, OutlineTypeConflictError
from .outline_single_phase import SinglePhaseOutlineError, stream_single_phase
from .outline_two_phase import TwoPhaseOutlineBuilder, TwoPhaseOutlineError

__all__ = [
    "OutlineGenerator",
    "OutlineGenerationError",
]

_PROMPTS_DIR = prompts_dir()

# 走两阶段的模式（其余走单阶段）
TWO_PHASE_TYPES = ("complete", "semi_open")


@lru_cache(maxsize=16)
def _load_outline_prompt(name: str) -> str:
    """加载 ``config/prompts/outline_{name}.yaml`` 的 ``prompt`` 字段。

    与 ``inspiration_service._load_prompt`` 类似；不抽公共（避免循环 import）。
    """
    path = _PROMPTS_DIR / f"outline_{name}.yaml"
    if not path.is_file():
        raise OutlineGenerationError(f"Outline prompt not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "prompt" not in data:
        raise OutlineGenerationError(f"Outline prompt {path} missing 'prompt' field")
    return str(data["prompt"])


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口。"""

    provider: str

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any: ...


class OutlineGenerator:
    """基于剧情生成大纲。

    职责：
    - 按模式选生成路径（两阶段 / 单阶段）
    - 调 LLM 生成结构化 JSON
    - 解析 + 校验（按 outline_type 走对应 Pydantic model）
    - 自动 upsert novel（按 name 查重）
    - 调 OutlineService.create 存到 DB
    - 失败抛 :class:`OutlineGenerationError`
    """

    def __init__(self, session: AsyncSession, llm_client: _LLMClientLike | None = None) -> None:
        self.session = session
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client

    def _get_llm(self, outline_type: str = "complete") -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            # 按 outline_type 精确路由（llm.yaml routing.outline_complete /
            # outline_freedom）。原 scene 名 "outline_generation" 在 routing 里
            # 不存在，一直静默回落 default_provider。
            self._llm = create_llm_client_for_scene(f"outline_{outline_type}")
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

    async def generate(
        self,
        genre: str,
        plot_summary: str,
        *,
        keywords: list[str] | None = None,
        novel_name: str | None = None,
        outline_type: str = "complete",
        user_extra: str = "",
        total_chapters: int | None = None,
        chapters_per_volume: int | None = None,
        words_per_chapter: int | None = None,
    ) -> dict[str, Any]:
        """生成大纲并入库（非流式）。

        :raises OutlineGenerationError: 任何一步失败
        """
        self._validate_request(outline_type, plot_summary)
        scale = normalize_scale(total_chapters, chapters_per_volume, words_per_chapter)

        llm = self._get_llm(outline_type)
        owns_client = self._llm_override is None
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")
        try:
            if outline_type in TWO_PHASE_TYPES:
                builder = TwoPhaseOutlineBuilder(
                    llm,
                    genre=genre,
                    plot_summary=plot_summary,
                    keywords=keywords or [],
                    scale=scale,
                    outline_type=outline_type,
                    user_extra=user_extra,
                )
                structure = await builder.build()
            else:
                structure = await self._generate_freedom(
                    llm, genre, plot_summary, keywords or [], user_extra
                )
        except OutlineGenerationError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed (outline): {}", describe_llm_error(e))
            raise OutlineGenerationError(describe_llm_error(e)) from e
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

        structure = self._validate_and_tag(outline_type, structure)

        name = await self._resolve_novel_name(genre, novel_name)
        novel = await self._upsert_novel(
            name=name,
            genre=genre,
            description=plot_summary[:500],
            outline_mode=outline_type,
        )
        outline = await self._save_outline(novel.id, outline_type, structure)
        return {
            "novel_id": novel.id,
            "novel_name": novel.name,
            "outline_id": outline.id,
            "outline_type": outline_type,
            "structure": structure,
            "provider": provider,
            "model": model,
        }

    # ===== 流式 =====

    async def stream_generate(
        self,
        genre: str,
        plot_summary: str,
        *,
        keywords: list[str] | None = None,
        novel_name: str | None = None,
        outline_type: str = "complete",
        user_extra: str = "",
        total_chapters: int | None = None,
        chapters_per_volume: int | None = None,
        words_per_chapter: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式生成大纲（边生成边推结构化增量，最后再入库）。

        协议见模块 docstring。
        """
        try:
            self._validate_request(outline_type, plot_summary)
        except OutlineGenerationError as e:
            yield {"event": "error", "message": str(e)}
            return

        scale = normalize_scale(total_chapters, chapters_per_volume, words_per_chapter)
        llm = self._get_llm(outline_type)
        owns_client = self._llm_override is None
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")
        t0 = time.monotonic()
        structure: dict[str, Any] | None = None
        first_delta_sec: float | None = None
        skeleton_sec: float | None = None

        yield {
            "event": "start",
            "phase": "outline",
            "outline_type": outline_type,
            "mode": "two_phase" if outline_type in TWO_PHASE_TYPES else "single_phase",
            "total_chapters": scale.total_chapters,
            "volume_count": scale.volume_count,
            "chapters_per_volume": scale.chapters_per_volume,
            "words_per_chapter": scale.words_per_chapter,
        }

        try:
            if outline_type in TWO_PHASE_TYPES:
                builder = TwoPhaseOutlineBuilder(
                    llm,
                    genre=genre,
                    plot_summary=plot_summary,
                    keywords=keywords or [],
                    scale=scale,
                    outline_type=outline_type,
                    user_extra=user_extra,
                )
                async for event in builder.run():
                    if event.get("event") == "structure_ready":
                        structure = event.get("structure")
                        first_delta_sec = event.get("first_delta_sec")
                        skeleton_sec = event.get("skeleton_sec")
                    yield event
            else:
                prompt = _load_outline_prompt(outline_type)
                async for event in stream_single_phase(
                    llm,
                    prompt_template=prompt,
                    genre=genre,
                    plot_summary=plot_summary,
                    keywords=keywords or [],
                    outline_type=outline_type,
                    user_extra=user_extra,
                ):
                    if event.get("event") == "structure_ready":
                        structure = event.get("structure")
                        first_delta_sec = event.get("first_delta_sec")
                    yield event
        except (TwoPhaseOutlineError, SinglePhaseOutlineError) as e:
            yield {"event": "error", "message": str(e)}
            return
        except Exception as e:  # noqa: BLE001
            logger.error("outline LLM stream failed: {}", describe_llm_error(e))
            yield {"event": "error", "message": describe_llm_error(e)}
            return
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

        if not isinstance(structure, dict) or not structure:
            yield {"event": "error", "message": "LLM returned empty structure"}
            return

        try:
            structure = self._validate_and_tag(outline_type, structure)
        except OutlineGenerationError as e:
            yield {"event": "error", "message": str(e)}
            return

        name = await self._resolve_novel_name(genre, novel_name)
        novel = await self._upsert_novel(
            name=name,
            genre=genre,
            description=plot_summary[:500],
            outline_mode=outline_type,
        )
        outline = await self._save_outline(novel.id, outline_type, structure)

        yield {
            "event": "done",
            "novel_id": novel.id,
            "novel_name": novel.name,
            "outline_id": outline.id,
            "outline_type": outline_type,
            "structure": structure,
            "provider": provider,
            "model": model,
            # 耗时（用户明确要求："添加生成当前模型耗时多少秒"）
            "elapsed_sec": round(time.monotonic() - t0, 2),
            "first_delta_sec": first_delta_sec,
            "skeleton_sec": skeleton_sec,
            "total_chapters": scale.total_chapters,
            "volume_count": scale.volume_count,
        }

    # ===== 内部 =====

    @staticmethod
    def _validate_request(outline_type: str, plot_summary: str) -> None:
        """校验入参；不合法直接抛 :class:`OutlineGenerationError`。"""
        if outline_type not in OUTLINE_TYPES:
            raise OutlineGenerationError(
                f"Invalid outline_type: {outline_type!r}; allowed: {OUTLINE_TYPES}"
            )
        if not plot_summary or len(plot_summary) < 10:
            raise OutlineGenerationError("plot_summary too short (>= 10 chars)")

    async def _generate_freedom(
        self,
        llm: _LLMClientLike,
        genre: str,
        plot_summary: str,
        keywords: list[str],
        user_extra: str,
    ) -> dict[str, Any]:
        """单阶段生成（``freedom`` 模式：散文 + 关键节拍 + 主题）。"""
        prompt = _load_outline_prompt("freedom")
        kw_str = ", ".join(keywords) if keywords else "（无）"
        extra_block = ""
        if user_extra.strip():
            extra_block = (
                f"\n\n【作者个人想法（请在生成时参考，但不要照搬）】\n{user_extra.strip()}\n"
            )
        full_prompt = prompt.format(genre=genre, plot=plot_summary, keywords=kw_str) + extra_block
        resp = await llm.chat([ChatMessage("user", full_prompt)], temperature=0.7)
        raw = resp.content if isinstance(resp.content, str) else ""
        if not raw.strip():
            raise OutlineGenerationError("LLM returned empty content")
        # 自动调用 scene=outline_generation 的 post-process skills
        # （仅作用于 LLM 原始输出；skill 应是 JSON-safe 的）
        post_cleaned = await skill_manager.apply_post("outline_generation", strip_thinking(raw))
        try:
            return extract_json_object(post_cleaned)
        except ValueError as e:
            raise OutlineGenerationError(f"JSON parse failed: {e}") from e

    def _validate_and_tag(self, outline_type: str, structure: dict[str, Any]) -> dict[str, Any]:
        """按 outline_type 校验 structure，并打上 ``outline_type`` 标记。"""
        outline_service = OutlineService(self.session)
        try:
            validated = outline_service._validate_structure(outline_type, structure)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            raise OutlineGenerationError(f"LLM output structure invalid: {e}") from e
        validated["outline_type"] = outline_type
        return validated

    async def _save_outline(
        self, novel_id: int, outline_type: str, structure: dict[str, Any]
    ) -> Any:
        """把结构存进 outlines 表（同 type 重复 → 先删旧的再创）。"""
        from ..schemas.outline import OutlineCreate

        outline_service = OutlineService(self.session)
        outline_payload = OutlineCreate(
            novel_id=novel_id,
            outline_type=outline_type,
            structure=structure,
        )
        try:
            return await outline_service.create(outline_payload)
        except OutlineTypeConflictError:
            existing = await outline_service.list_all(novel_id=novel_id, outline_type=outline_type)
            for o in existing:
                await outline_service.delete(o.id)
            return await outline_service.create(outline_payload)

    async def _upsert_novel(
        self,
        *,
        name: str,
        genre: str,
        description: str,
        outline_mode: str | None = None,
    ) -> Novel:
        """按 name 查重 novel。已存在 → 复用；否则创建。

        :param outline_mode: 大纲模式（complete / semi_open / freedom）——
            写进 novel，章节生成 prompt 会带上它（半开放式写出来的章节
            要"只写前期、留悬念"，不能自己把故事写完）。
        """
        existing = await self.session.execute(select(Novel).where(Novel.name == name))
        novel = existing.scalar_one_or_none()
        if novel is not None:
            return novel
        novel = Novel(
            name=name,
            genre=genre,
            description=description,
            outline_mode=outline_mode,
        )
        self.session.add(novel)
        await self.session.flush()
        await self.session.refresh(novel)
        return novel

    async def _resolve_novel_name(self, genre: str, novel_name: str | None) -> str:
        """确定这次要用的作品名。

        - **显式给了名字** → 原样用。同名会命中 :meth:`_upsert_novel` 的复用逻辑，
          这正是"重新生成这本的大纲"的语义。
        - **没给名字** → 生成**唯一**名字（``修仙新作`` / ``修仙新作 2`` …）。

        ⚠️ 2026-10-25 巡检发现的**阻断级 bug**：这里原来直接用 ``f"{genre}新作"``，
        而前端从不传书名 → 第二次用同题材走「开新书」会**复用第一本书**，
        然后"同 type 覆盖"把第一本的大纲删掉重建、人物卡也写进第一本的 novel_id
        —— 用户的第一本书被静默毁掉。
        """
        explicit = (novel_name or "").strip()
        if explicit:
            return explicit
        base = f"{genre}新作"
        name = base
        index = 1
        while await self._novel_exists(name):
            index += 1
            name = f"{base} {index}"
        return name

    async def _novel_exists(self, name: str) -> bool:
        """同名作品是否已存在。"""
        result = await self.session.execute(select(Novel.id).where(Novel.name == name).limit(1))
        return result.scalar_one_or_none() is not None

    @staticmethod
    def clear_prompt_cache() -> None:
        """测试用：清 prompt lru_cache。"""
        _load_outline_prompt.cache_clear()
