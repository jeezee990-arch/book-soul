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

from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, ChatResponse
from ..core.llm.formatting import extract_json_object
from ..models.novel import Novel
from ..models.outline import OUTLINE_TYPES
from .outline_service import OutlineService, OutlineTypeConflictError


def _find_repo_root() -> Path:
    """向上找项目根：包含 ``config/`` + ``pyproject.toml``。"""
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    return Path(__file__).resolve().parents[4]


_PROMPTS_DIR = _find_repo_root() / "config" / "prompts"


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

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("outline_generation")
        return self._llm

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

        structure = await self._call_llm(genre, plot_summary, keywords or [], outline_type)

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

        # 取 provider 信息（用于响应）
        try:
            llm = self._get_llm()
            provider = getattr(llm, "provider", "unknown")
            model = getattr(llm, "model", "")
        except Exception:  # noqa: BLE001
            provider = "unknown"
            model = ""

        return {
            "novel_id": novel.id,
            "novel_name": novel.name,
            "outline_id": outline.id,
            "outline_type": outline_type,
            "structure": structure,
            "provider": provider,
            "model": model,
        }

    # ===== 内部 =====

    async def _call_llm(
        self,
        genre: str,
        plot_summary: str,
        keywords: list[str],
        outline_type: str,
    ) -> dict[str, Any]:
        prompt = _load_outline_prompt(outline_type)
        kw_str = ", ".join(keywords) if keywords else "（无）"
        full_prompt = prompt.format(genre=genre, plot=plot_summary, keywords=kw_str)
        llm = self._get_llm()
        try:
            resp = await llm.chat(
                [ChatMessage("user", full_prompt)],
                temperature=0.7,
            )
        except Exception as e:  # noqa: BLE001
            # Phase 3.4 修：与 inspiration_service 同步：暴露异常类型 + body
            # （minimax 海外节点抛 httpx.TimeoutException 时 str(e) 可能是空）
            err_type = type(e).__name__
            extra = ""
            resp_obj = getattr(e, "response", None)
            if resp_obj is not None:
                try:
                    body = (resp_obj.text or "")[:200]
                    extra = f" body={body!r}"
                except Exception:  # noqa: BLE001
                    pass
            logger.error(f"LLM call failed (outline): {err_type}: {e}{extra}")
            raise OutlineGenerationError(f"LLM call failed: {err_type}: {e}{extra}") from e
        raw = resp.content if isinstance(resp.content, str) else ""
        if not raw.strip():
            raise OutlineGenerationError("LLM returned empty content")
        try:
            return extract_json_object(raw)
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


# 兼容性别名：让 ``from src.services.outline_generator import ...`` 一目了然
__all__ = [
    "OutlineGenerator",
    "OutlineGenerationError",
]
