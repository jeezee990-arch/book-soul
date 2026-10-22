"""Inspiration 业务服务（Phase 1.5 灵感库 CRUD + Phase 3.3 剧情生成）。

设计：
- novel_id 可空：通用灵感（novel_id=None）vs 作品灵感
- 不分版本：灵感不演化
- content 按 type 校验形状（service 层用对应 Pydantic model）
- tags 简单 list[str]
- 剧情生成：``PlotService``（不依赖 session），调 LLM 抽象生成简短剧情
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Protocol

import yaml
from loguru import logger
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.llm.base import ChatMessage, ChatResponse, describe_llm_error
from ..core.paths import prompts_dir
from ..core.skills import manager as skill_manager
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


_PROMPTS_DIR = prompts_dir()


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

    async def aclose(self) -> None: ...


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
        """生成 n 个简要剧情版本（并行调用，总耗时 ≈ 单次）。

        :raises PlotGenerationError: LLM 调用失败 / prompt 缺失 / 返回为空
        """
        if not keywords:
            raise PlotGenerationError("keywords must not be empty")
        if n_versions < 1:
            raise PlotGenerationError(f"n_versions must be >= 1, got {n_versions}")

        template = _load_prompt("plot_generation")
        prompt = template.format(genre=genre, keywords=", ".join(keywords))
        llm = self._get_llm()
        # 注入的客户端（测试 mock）不由本方法关闭；懒加载的用完即关
        owns_client = self._llm_override is None
        try:
            # 各版本相互独立，并行调用（原串行 3 次 × ~30s 是"生成慢"主因）
            raws = await asyncio.gather(*(self._chat_once(llm, prompt) for _ in range(n_versions)))
        except Exception as e:  # noqa: BLE001
            logger.error(describe_llm_error(e))
            raise PlotGenerationError(describe_llm_error(e)) from e
        finally:
            await self._release_llm(llm, owns_client)

        results: list[str] = []
        for raw in raws:
            content = _strip_thinking(raw.strip())
            if not content:
                raise PlotGenerationError("LLM returned empty content")
            results.append(content)
        return results

    @staticmethod
    async def _chat_once(llm: _LLMClientLike, prompt: str) -> str:
        """单次 LLM 调用，返回原始文本（空 content 返回空串，由调用方判定）。"""
        resp = await llm.chat([ChatMessage("user", prompt)], temperature=0.8)
        return resp.content if isinstance(resp.content, str) else ""

    def _build_prompt(
        self,
        genre: str,
        keywords: list[str],
        *,
        user_extra: str = "",
    ) -> str:
        """构造 LLM 输入 prompt（含 ``user_extra`` 注入）。"""
        template = _load_prompt("plot_generation")
        extra_block = ""
        if user_extra.strip():
            extra_block = (
                f"\n\n【作者个人想法（请在生成时参考，但不要照搬）】\n{user_extra.strip()}\n"
            )
        return template.format(genre=genre, keywords=", ".join(keywords)) + extra_block

    async def stream_generate(
        self,
        genre: str,
        keywords: list[str],
        n_versions: int = DEFAULT_N_VERSIONS,
        *,
        user_extra: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """流式生成 n 个简要剧情版本（Phase 性能优化）。

        协议（与 ``_stream_helpers.ndjson_line`` 配合）：

        - ``{"event": "version_start", "index": i}``
        - ``{"event": "delta", "index": i, "text": "..."}``（每条 delta）
        - ``{"event": "version_done", "index": i, "summary": "..."}``（该版本完成）
        - ``{"event": "done", "provider": "...", "model": "..."}``（全部完成）

        失败：
        - ``{"event": "error", "message": "..."}``

        行为：每个版本独立调 LLM，多个版本并行；
        每个版本的 stream token 实时 push 给前端；
        整流完成后统一发 ``done``。
        """
        if not keywords:
            yield {"event": "error", "message": "keywords must not be empty"}
            return
        if n_versions < 1:
            yield {"event": "error", "message": f"n_versions must be >= 1, got {n_versions}"}
            return

        prompt = self._build_prompt(genre, keywords, user_extra=user_extra)
        # 流式版使用缓存单例（不关闭 → httpx 连接池复用）
        from ..core.llm import get_cached_llm_client

        if self._llm_override is not None:
            llm = self._llm_override  # 测试 mock
            owns_client = True
        else:
            llm = get_cached_llm_client("plot_generation")
            owns_client = False
        provider = getattr(llm, "provider", "unknown")
        model = getattr(llm, "model", "")

        # 每个版本独立 task；内部用 asyncio.Queue 把 token 透出
        queues: list[asyncio.Queue[dict[str, Any] | None]] = [
            asyncio.Queue() for _ in range(n_versions)
        ]

        async def version_runner(idx: int) -> None:
            """单版本流式 LLM 调用，结果塞到自己的 queue。"""
            q = queues[idx]
            full_text = ""
            try:
                stream = await llm.chat(
                    [ChatMessage("user", prompt)],
                    temperature=0.8,
                    stream=True,
                )
                # OpenAI 兼容流式：stream 是 ``AsyncIterator[str]``（每个 delta 文本）
                async for delta in stream:  # type: ignore[union-attr]
                    if not delta:
                        continue
                    # 过滤跨 chunk 的 <think> 推理块
                    if "<think>" in delta and "</think>" not in delta:
                        continue
                    full_text += delta
                    await q.put({"event": "delta", "index": idx, "text": delta})
                raw_summary = _strip_thinking(full_text)
                if not raw_summary:
                    await q.put({"event": "error", "message": f"version {idx} empty"})
                else:
                    # 自动调用 scene=plot_generation 的 post-process skills（默认 sensitive_word）
                    cleaned_summary = await skill_manager.apply_post("plot_generation", raw_summary)
                    await q.put({"event": "version_done", "index": idx, "summary": cleaned_summary})
            except Exception as e:  # noqa: BLE001
                logger.error("plot version {} failed: {}", idx, describe_llm_error(e))
                await q.put({"event": "error", "message": describe_llm_error(e)})
            finally:
                await q.put(None)  # 哨兵

        tasks = [asyncio.create_task(version_runner(i + 1)) for i in range(n_versions)]
        # 先发所有 version_start
        for i in range(n_versions):
            yield {"event": "version_start", "index": i + 1}
        # 轮询所有 queue，按事件实际到达顺序透出
        finished = 0
        try:
            while finished < n_versions:
                # 并发等待下一个事件
                get_tasks = [asyncio.create_task(q.get()) for q in queues]
                done, _ = await asyncio.wait(get_tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    payload = t.result()
                    if payload is None:
                        finished += 1
                    else:
                        yield payload
                    # 取消未完成的 get 任务
                    for pending in _:
                        pending.cancel()
        finally:
            # 等待所有 runner 退出
            await asyncio.gather(*tasks, return_exceptions=True)
            if owns_client:
                await self._release_llm(llm, owns=True)

        yield {"event": "done", "provider": provider, "model": model}

    async def _release_llm(self, llm: _LLMClientLike, owns: bool) -> None:
        """懒加载的客户端用完关闭（防连接泄漏），并清缓存让下次重建。"""
        aclose = getattr(llm, "aclose", None)
        if owns and aclose is not None:
            try:
                await aclose()
            finally:
                self._llm = None

    @staticmethod
    def clear_prompt_cache() -> None:
        """测试用：清 prompt lru_cache。"""
        _load_prompt.cache_clear()
