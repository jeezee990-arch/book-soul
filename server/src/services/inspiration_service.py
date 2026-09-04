"""Inspiration 业务服务（Phase 1.5 灵感库 CRUD + Phase 3.3 剧情生成）。

设计：
- novel_id 可空：通用灵感（novel_id=None）vs 作品灵感
- 不分版本：灵感不演化
- content 按 type 校验形状（service 层用对应 Pydantic model）
- tags 简单 list[str]
- 剧情生成：``PlotService``（不依赖 session），调 LLM 抽象生成简短剧情
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, ChatResponse
from ..models.inspiration import INSPIRATION_TYPES, Inspiration
from ..models.novel import Novel
from ..schemas.inspiration import (
    ImageContent,
    InspirationCreate,
    InspirationUpdate,
    KeywordContent,
    NoteContent,
    PlotContent,
    SnippetContent,
)


def _content_model_for(inspiration_type: str) -> type[BaseModel]:
    """按 type 返回对应的 content Pydantic model。"""
    if inspiration_type == "keyword":
        return KeywordContent
    if inspiration_type == "plot":
        return PlotContent
    if inspiration_type == "snippet":
        return SnippetContent
    if inspiration_type == "image":
        return ImageContent
    if inspiration_type == "note":
        return NoteContent
    raise InspirationValidationError(  # noqa: F821
        f"Unknown type: {inspiration_type!r}; allowed: {INSPIRATION_TYPES}"
    )


def _tag_like_pattern(tag: str) -> str:
    """把 tag 转成 SQL LIKE 模式，匹配 SQLAlchemy 存 JSON 的实际格式。

    SQLAlchemy 存 JSON 数组用 ensure_ascii=True（``json.dumps`` 默认），
    所以 `["热门"]` 存为 `["\\u70ed\\u95e8"]`。我们要 LIKE 的话也得用
    同样的转义形式。
    """
    inner = json.dumps([tag], ensure_ascii=True)[1:-1]  # 去掉 []
    return f"%{inner}%"


class InspirationServiceError(Exception):
    """Service 层基础异常。"""


class InspirationNotFoundError(InspirationServiceError):
    def __init__(self, inspiration_id: int) -> None:
        super().__init__(f"Inspiration {inspiration_id} not found")
        self.inspiration_id = inspiration_id


class NovelNotFoundError(InspirationServiceError):
    def __init__(self, novel_id: int) -> None:
        super().__init__(f"Novel {novel_id} not found")
        self.novel_id = novel_id


class InspirationValidationError(InspirationServiceError):
    """字段取值非法。"""


class InspirationService:
    """灵感库 CRUD 服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ===== 校验辅助 =====
    @staticmethod
    def _validate_type(inspiration_type: str | None) -> None:
        if inspiration_type is not None and inspiration_type not in INSPIRATION_TYPES:
            raise InspirationValidationError(
                f"Invalid type: {inspiration_type!r}; allowed: {INSPIRATION_TYPES}"
            )

    def _validate_content(self, inspiration_type: str, content: dict) -> dict:
        """按 type 校验 content 形状，返回 validated dict（不含 None 字段）。"""
        model = _content_model_for(inspiration_type)
        try:
            validated = model.model_validate(content)
        except ValidationError as e:
            raise InspirationValidationError(
                f"Invalid content for type {inspiration_type!r}: {e}"
            ) from e
        return validated.model_dump(exclude_none=True)

    async def _ensure_novel_exists_if_given(self, novel_id: int | None) -> None:
        if novel_id is not None:
            novel = await self.session.get(Novel, novel_id)
            if novel is None:
                raise NovelNotFoundError(novel_id)

    # ===== 业务方法 =====
    async def create(self, data: InspirationCreate) -> Inspiration:
        """创建灵感。"""
        self._validate_type(data.type)
        await self._ensure_novel_exists_if_given(data.novel_id)
        content = self._validate_content(data.type, data.content)

        inspiration = Inspiration(
            novel_id=data.novel_id,
            type=data.type,
            content=content,
            source=data.source,
            tags=list(data.tags),
        )
        self.session.add(inspiration)
        await self.session.commit()
        await self.session.refresh(inspiration)
        return inspiration

    async def get(self, inspiration_id: int) -> Inspiration:
        """按 id 查询；不存在抛 NotFound。"""
        inspiration = await self.session.get(Inspiration, inspiration_id)
        if inspiration is None:
            raise InspirationNotFoundError(inspiration_id)
        return inspiration

    async def list_all(
        self,
        *,
        novel_id: int | None = None,
        inspiration_type: str | None = None,
        tag: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Inspiration]:
        """列出灵感，支持 novel_id / type / tag 过滤。"""
        self._validate_type(inspiration_type)
        stmt = select(Inspiration)
        # novel_id 过滤：None 表示仅通用灵感；int 表示该作品
        if novel_id is not None:
            stmt = stmt.where(Inspiration.novel_id == novel_id)
        if inspiration_type is not None:
            stmt = stmt.where(Inspiration.type == inspiration_type)
        # tag 过滤用 JSON LIKE（SQLite 简单实现；转义保证中英文都能匹配）
        if tag is not None:
            stmt = stmt.where(Inspiration.tags.like(_tag_like_pattern(tag)))
        stmt = stmt.order_by(Inspiration.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def update(self, inspiration_id: int, data: InspirationUpdate) -> Inspiration:
        """部分更新。改 type 时要重新校验 content。"""
        inspiration = await self.get(inspiration_id)
        updates = data.model_dump(exclude_unset=True)
        if "type" in updates:
            self._validate_type(updates["type"])
        if "novel_id" in updates:
            await self._ensure_novel_exists_if_given(updates["novel_id"])
        if "content" in updates and updates["content"] is not None:
            # 用最终 type 校验（可能同时改了 type）
            type_to_validate = updates.get("type", inspiration.type)
            updates["content"] = self._validate_content(type_to_validate, updates["content"])
        for key, value in updates.items():
            setattr(inspiration, key, value)
        await self.session.commit()
        await self.session.refresh(inspiration)
        return inspiration

    async def delete(self, inspiration_id: int) -> None:
        """删除。幂等。"""
        inspiration = await self.session.get(Inspiration, inspiration_id)
        if inspiration is not None:
            await self.session.delete(inspiration)
            await self.session.commit()


# =====================================================================
# Phase 3.3：剧情生成（独立类，不依赖 session，调 LLM 抽象）
# =====================================================================


def _find_repo_root() -> Path:
    """向上找项目根：包含 ``config/`` + ``pyproject.toml``。"""
    p = Path(__file__).resolve().parent
    for _ in range(8):
        if (p / "config").is_dir() and (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    return Path(__file__).resolve().parents[4]


_PROMPTS_DIR = _find_repo_root() / "config" / "prompts"


@lru_cache(maxsize=8)
def _load_prompt(name: str) -> str:
    """加载 ``config/prompts/{name}.yaml`` 的 ``prompt`` 字段。

    缓存到 lru_cache；测试可用 ``_load_prompt.cache_clear()`` 清除。
    """
    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.is_file():
        raise PlotGenerationError(f"Prompt file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "prompt" not in data:
        raise PlotGenerationError(f"Prompt file {path} missing 'prompt' field")
    return str(data["prompt"])


class _LLMClientLike(Protocol):
    """LLM 客户端最小接口（用于注入和 mock）。"""

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


class PlotGenerationError(Exception):
    """剧情生成失败（含 LLM 错误、prompt 缺失等）。"""


def _strip_thinking(text: str) -> str:
    """剥掉 LLM 输出的 ``<think>...</think>`` 推理块（minimax 推理模型会输出）。

    如果没有 think 块，原样返回。多次匹配（一般 1 次足够）。
    """
    import re

    cleaned = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)
    return cleaned.strip()


class PlotService:
    """剧情生成服务（Phase 3.3）。

    职责：
    - 加载 plot_generation prompt 模板
    - 串行调用 LLM 生成 n 个版本
    - 失败 → :class:`PlotGenerationError`，由 API 层映射 500/422

    设计：
    - 接受可选 ``llm_client`` 注入（测试用 mock）
    - 默认用 ``create_llm_client_for_scene("plot_generation")`` 懒加载
    - 不依赖 DB（生成结果不入库，由前端决定是否保存）
    """

    DEFAULT_N_VERSIONS = 3

    def __init__(self, llm_client: _LLMClientLike | None = None) -> None:
        self._llm_override = llm_client
        self._llm: _LLMClientLike | None = llm_client  # 懒加载

    def _get_llm(self) -> _LLMClientLike:
        if self._llm is None:
            # 懒加载（避免 import 时强制初始化 LLM）
            from ..core.llm import create_llm_client_for_scene

            self._llm = create_llm_client_for_scene("plot_generation")
        return self._llm

    async def generate(
        self,
        genre: str,
        keywords: list[str],
        n_versions: int = DEFAULT_N_VERSIONS,
    ) -> list[str]:
        """生成 n 个简要剧情版本。

        :raises PlotGenerationError: LLM 调用失败 / prompt 缺失 / 返回为空
        """
        if not keywords:
            raise PlotGenerationError("keywords must not be empty")
        if n_versions < 1:
            raise PlotGenerationError(f"n_versions must be >= 1, got {n_versions}")

        template = _load_prompt("plot_generation")
        prompt = template.format(genre=genre, keywords=", ".join(keywords))
        llm = self._get_llm()
        results: list[str] = []
        for _ in range(n_versions):
            try:
                resp = await llm.chat(
                    [ChatMessage("user", prompt)],
                    temperature=0.8,
                )
            except Exception as e:  # noqa: BLE001
                # Phase 3.4 修：minimax 偶尔抛 httpx.TimeoutException / TransportError，
                # str(e) 可能是空字符串，导致上层看到的 message 是 "LLM call failed: "。
                # 修法：把异常类型 + response body 拼进去，至少能看到是哪种错误。
                err_type = type(e).__name__
                extra = ""
                resp_obj = getattr(e, "response", None)
                if resp_obj is not None:
                    try:
                        body = (resp_obj.text or "")[:200]
                        extra = f" body={body!r}"
                    except Exception:  # noqa: BLE001
                        pass
                logger.error(f"LLM call failed: {err_type}: {e}{extra}")
                raise PlotGenerationError(f"LLM call failed: {err_type}: {e}{extra}") from e
            raw = resp.content.strip() if isinstance(resp.content, str) else ""
            if not raw:
                raise PlotGenerationError("LLM returned empty content")
            content = _strip_thinking(raw)
            if not content:
                raise PlotGenerationError("LLM output empty after stripping thinking")
            results.append(content)
        return results

    @staticmethod
    def clear_prompt_cache() -> None:
        """测试用：清 prompt lru_cache。"""
        _load_prompt.cache_clear()
