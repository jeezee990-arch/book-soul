"""基于剧情生成大纲（Phase 3.4）。

设计：
- 加载 ``config/prompts/outline_{complete,freedom}.yaml`` 模板（lru_cache）
- 调 LLM 抽象生成结构化 JSON
- 后处理：strip thinking 块 + extract JSON object
- 自动 upsert novel（按 novel_name 查重，缺省 ``"{genre}新作"``）
- 把结果存到 Outline 表（OutlineService.create）
- 失败 → :class:`OutlineGenerationError`

不做的事：
- 不直接修改 outline_service.py（保持其文件 ≤ 300 行）
- 不依赖 inspiration_service（避免循环 import）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, ChatResponse, describe_llm_error
from ..core.llm.formatting import extract_json_object, strip_thinking
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.paths import prompts_dir
from ..core.skills import manager as skill_manager
from ..models.novel import Novel
from ..models.outline import OUTLINE_TYPES
from .outline_service import OutlineService, OutlineTypeConflictError

_PROMPTS_DIR = prompts_dir()


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
    ) -> ChatResponse: ...


class OutlineGenerationError(Exception):
    """大纲生成失败。"""


class OutlineGenerator:
    """基于剧情生成大纲（Phase 3.4）。

    职责：
    - 加载 outline_{complete,freedom} prompt 模板
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
    ) -> dict[str, Any]:
        """生成大纲并入库。

        流程：
        1. 调 LLM 生成 structure
        2. 解析 JSON + 校验
        3. upsert novel（按 name）
        4. OutlineService.create（已含 type 冲突检查）

        :raises OutlineGenerationError: 任何一步失败
        """
        if outline_type not in OUTLINE_TYPES:
            raise OutlineGenerationError(
                f"Invalid outline_type: {outline_type!r}; allowed: {OUTLINE_TYPES}"
            )
        if not plot_summary or len(plot_summary) < 10:
            raise OutlineGenerationError("plot_summary too short (>= 10 chars)")

        structure, llm_provider, llm_model = await self._call_llm(
            genre, plot_summary, keywords or [], outline_type
        )

        # 校验 structure（复用 OutlineService 的校验逻辑）
        outline_service = OutlineService(self.session)
        try:
            structure = outline_service._validate_structure(outline_type, structure)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            raise OutlineGenerationError(f"LLM output structure invalid: {e}") from e
        structure["outline_type"] = outline_type

        # upsert novel
        name = (novel_name or f"{genre}新作").strip() or f"{genre}新作"
        novel = await self._upsert_novel(name=name, genre=genre, description=plot_summary[:500])

        # 存 outline（OutlineService 内部会校验同 type 冲突）
        from ..schemas.outline import OutlineCreate

        outline_payload = OutlineCreate(
            novel_id=novel.id,
            outline_type=outline_type,
            structure=structure,
        )
        try:
            outline = await outline_service.create(outline_payload)
        except OutlineTypeConflictError:
            # 已有同 type → 删除旧的再创（重生覆盖语义）
            existing = await outline_service.list_all(novel_id=novel.id, outline_type=outline_type)
            for o in existing:
                await outline_service.delete(o.id)
            outline = await outline_service.create(outline_payload)

        return {
            "novel_id": novel.id,
            "novel_name": novel.name,
            "outline_id": outline.id,
            "outline_type": outline_type,
            "structure": structure,
            "provider": llm_provider,
            "model": llm_model,
        }

    # ===== 内部 =====

    async def _call_llm(
        self,
        genre: str,
        plot_summary: str,
        keywords: list[str],
        outline_type: str,
    ) -> tuple[dict[str, Any], str, str]:
        """调 LLM 并解析 structure，返回 ``(structure, provider, model)``。"""
        prompt = _load_outline_prompt(outline_type)
        kw_str = ", ".join(keywords) if keywords else "（无）"
        full_prompt = prompt.format(genre=genre, plot=plot_summary, keywords=kw_str)
        llm = self._get_llm(outline_type)
        owns_client = self._llm_override is None
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")
        try:
            resp = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.7,
            )
        except Exception as e:  # noqa: BLE001
            logger.error("LLM call failed (outline): {}", describe_llm_error(e))
            raise OutlineGenerationError(describe_llm_error(e)) from e
        finally:
            await self._release_llm(llm, owns_client)
        raw = resp.content if isinstance(resp.content, str) else ""
        if not raw.strip():
            raise OutlineGenerationError("LLM returned empty content")
        try:
            return extract_json_object(raw), provider, model
        except ValueError as e:
            raise OutlineGenerationError(str(e)) from e

    async def _upsert_novel(
        self,
        *,
        name: str,
        genre: str,
        description: str,
    ) -> Novel:
        """按 name 查重 novel。已存在 → 复用；否则创建。"""
        existing = await self.session.execute(select(Novel).where(Novel.name == name))
        novel = existing.scalar_one_or_none()
        if novel is not None:
            return novel
        novel = Novel(name=name, genre=genre, description=description)
        self.session.add(novel)
        await self.session.flush()
        await self.session.refresh(novel)
        return novel

    @staticmethod
    def clear_prompt_cache() -> None:
        """测试用：清 prompt lru_cache。"""
        _load_outline_prompt.cache_clear()

    # ===== 流式（Phase 性能优化）=====

    async def stream_generate(
        self,
        genre: str,
        plot_summary: str,
        *,
        keywords: list[str] | None = None,
        novel_name: str | None = None,
        outline_type: str = "complete",
        user_extra: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """流式生成大纲（边生成边推 token，最后再解析 + 入库）。

        协议：
        - ``{"event": "start", "phase": "outline"}``
        - ``{"event": "delta", "text": "..."}``（每条 token；前端累加显示）
        - ``{"event": "done", "novel_id": ..., "outline_id": ..., "novel_name": ..., "structure": ..., "provider": "...", "model": "..."}``
        - ``{"event": "error", "message": "..."}``
        """
        if outline_type not in OUTLINE_TYPES:
            yield {"event": "error", "message": f"invalid outline_type: {outline_type!r}"}
            return
        if not plot_summary or len(plot_summary) < 10:
            yield {"event": "error", "message": "plot_summary too short (>= 10 chars)"}
            return

        prompt = _load_outline_prompt(outline_type)
        kw_str = ", ".join(keywords or []) if keywords else "（无）"
        extra_block = ""
        if user_extra.strip():
            extra_block = (
                f"\n\n【作者个人想法（请在生成时参考，但不要照搬）】\n{user_extra.strip()}\n"
            )
        full_prompt = prompt.format(genre=genre, plot=plot_summary, keywords=kw_str) + extra_block

        llm = self._get_llm(outline_type)
        owns_client = self._llm_override is None
        provider = str(getattr(llm, "provider", "unknown") or "unknown")
        model = str(getattr(llm, "model", "") or "")

        yield {"event": "start", "phase": "outline", "outline_type": outline_type}

        full_text = ""
        # 思考阶段用状态机拆出来 —— 思考可能持续好几秒，
        # 直接丢掉的话前端这段时间一个字都收不到（用户看到"卡住不动"）。
        # 这里转发成 "thinking" 事件，前端显示"模型思考中…"。
        splitter = ThinkSplitter()
        try:
            stream = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.7,
                stream=True,
            )
            async for delta in stream:  # type: ignore[union-attr]
                if not delta:
                    continue
                for kind, text in splitter.feed(delta):
                    if kind == KIND_THINK:
                        yield {"event": "thinking", "text": text}
                        continue
                    full_text += text
                    yield {"event": "delta", "text": text}
        except Exception as e:  # noqa: BLE001
            logger.error("outline LLM stream failed: {}", describe_llm_error(e))
            yield {"event": "error", "message": describe_llm_error(e)}
            return
        finally:
            if owns_client:
                await self._release_llm(llm, owns=True)

        cleaned = strip_thinking(full_text)
        if not cleaned:
            yield {"event": "error", "message": "LLM returned empty"}
            return

        # 自动调用 scene=outline_generation 的 post-process skills（仅作用于 LLM 原始输出）
        # skill 应是 JSON-safe 的（substring-based）；若破坏 JSON 解析会 fallback 原文
        post_cleaned = await skill_manager.apply_post("outline_generation", cleaned)

        try:
            structure = extract_json_object(post_cleaned)
        except ValueError as e:
            yield {"event": "error", "message": f"JSON parse failed: {e}"}
            return

        outline_service = OutlineService(self.session)
        try:
            structure = outline_service._validate_structure(outline_type, structure)  # noqa: SLF001
        except Exception as e:  # noqa: BLE001
            yield {"event": "error", "message": f"structure invalid: {e}"}
            return
        structure["outline_type"] = outline_type

        name = (novel_name or f"{genre}新作").strip() or f"{genre}新作"
        novel = await self._upsert_novel(name=name, genre=genre, description=plot_summary[:500])

        from ..schemas.outline import OutlineCreate

        outline_payload = OutlineCreate(
            novel_id=novel.id,
            outline_type=outline_type,
            structure=structure,
        )
        try:
            outline = await outline_service.create(outline_payload)
        except OutlineTypeConflictError:
            existing = await outline_service.list_all(novel_id=novel.id, outline_type=outline_type)
            for o in existing:
                await outline_service.delete(o.id)
            outline = await outline_service.create(outline_payload)

        yield {
            "event": "done",
            "novel_id": novel.id,
            "novel_name": novel.name,
            "outline_id": outline.id,
            "outline_type": outline_type,
            "structure": structure,
            "provider": provider,
            "model": model,
        }


# 兼容性别名：让 ``from src.services.outline_generator import ...`` 一目了然
__all__ = [
    "OutlineGenerator",
    "OutlineGenerationError",
]
