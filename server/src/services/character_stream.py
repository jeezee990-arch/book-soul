"""人物卡的**流式**生成（Phase 性能优化）。

为什么单独一个文件
------------------
人物卡生成有两条路径：

- **非流式**（:meth:`src.services.character_generator.CharacterGenerator.generate_from_outline`）
  —— 一次性抽人物 + 一次性生成全部卡 + 入库。
- **流式**（本模块）—— 边抽边推、每张卡实时生成 + 实时入库。

两条路径共用 prompt 模板与解析逻辑，但流式路径多了一整套并发/事件协议
（queue、入库锁、事件合并）。挤在一个文件里两边都会超 500 行
（AGENTS.md §8.1），所以按路径拆开。

⚠️ 写库必须串行（AGENTS.md §4.8）
--------------------------------
所有卡共用一个 ``AsyncSession``，而 ``AsyncSession`` **不是并发安全的** ——
两张卡同时 flush/commit 会抛 ``InvalidRequestError: Session is already flushing``，
结果就是"4 张卡只存进去 1 张"（2026-10-24 实测复现）。
LLM 调用（最耗时的部分）保持并行，只把入库这一小段用锁串起来。

⚠️ 思考内容要净身（2026-10-29）
-------------------------------
模型思考里常混着英文规划文字，直接转发会漏到前端卡片上。
统一走 :func:`src.core.llm.thinking.thinking_event` 洗成纯中文。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..core.llm.base import ChatMessage, describe_llm_error
from ..core.llm.formatting import extract_json_array, extract_yaml_block, strip_thinking
from ..core.llm.streaming import KIND_THINK, ThinkSplitter
from ..core.llm.thinking import thinking_event
from ..core.queue_merge import merge_queue_events
from ..core.skills import manager as skill_manager
from ._character_helpers import CharacterGenerationError, _normalize_role, _trim_to_str
from .character_service import CharacterService

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查时导入，避免循环 import
    from .character_generator import CharacterGenerator

__all__ = ["CardQueueHandle", "stream_generate_from_outline"]


class CardQueueHandle:
    """单张卡的流式句柄：内部 queue + producer task + name。"""

    __slots__ = ("name", "q", "task")

    def __init__(self, name: str, q: asyncio.Queue, task: asyncio.Task) -> None:
        self.name = name
        self.q = q
        self.task = task


def _build_card_prompt(
    *,
    name: str,
    role: str,
    genre: str,
    outline: dict,
    user_extra: str = "",
    load_prompt: Any,
) -> str:
    """构造单卡 prompt（含 user_extra）。

    :param load_prompt: prompt 加载函数（由调用方注入，避免跨模块 import 环）
    """
    template = load_prompt("generate_card")
    outline_ctx = json.dumps(outline, ensure_ascii=False)
    if len(outline_ctx) > 2000:
        outline_ctx = outline_ctx[:2000] + "\n... (truncated)"
    prompt = template.format(name=name, role=role, genre=genre, outline_context=outline_ctx)
    if user_extra.strip():
        prompt += f"\n\n【作者个人想法（参考即可）】\n{user_extra.strip()}\n"
    return prompt


async def stream_generate_from_outline(
    gen: CharacterGenerator,
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
    load_prompt = gen.load_prompt
    if not isinstance(outline, dict):
        yield {"event": "error", "message": "outline must be dict"}
        return
    if not genre:
        yield {"event": "error", "message": "genre must be non-empty"}
        return

    char_service = CharacterService(gen.session)
    try:
        await char_service._ensure_novel_exists(novel_id)  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        yield {"event": "error", "message": f"novel not found: {e}"}
        return

    # 流式版：使用缓存单例（不释放 → httpx 连接复用）
    if gen.llm_override is not None:
        llm = gen.llm_override
        owns_client = True
    else:
        from ..core.llm import get_cached_llm_client

        llm = get_cached_llm_client("character_generation")
        gen.llm = llm
        owns_client = False
    provider = str(getattr(llm, "provider", "unknown") or "unknown")
    model = str(getattr(llm, "model", "") or "")

    yield {"event": "phase", "phase": "extract"}
    # 整个流程的计时起点（用户要求显示"当前模型耗时多少秒"）
    t0 = time.monotonic()

    # Step 1: 流式抽取人物
    extracted: list[dict[str, str]] = []
    try:
        template = load_prompt("extract_characters")
        outline_str = json.dumps(outline, ensure_ascii=False, indent=2)
        extra_block = ""
        if user_extra.strip():
            extra_block = f"\n\n【作者个人想法（请在生成时参考）】\n{user_extra.strip()}\n"
        extract_prompt = template.format(outline=outline_str) + extra_block
        full_text = ""
        # 思考阶段用状态机拆出来 —— 思考期间不能一个字都不发
        # （前端会显示"模型思考中…"而不是"卡住不动"）。
        splitter = ThinkSplitter()
        stream = await llm.chat(
            [ChatMessage("user", extract_prompt)],
            temperature=0.5,
            stream=True,
        )
        async for delta in stream:
            if not delta:
                continue
            for kind, text in splitter.feed(delta):
                if kind == KIND_THINK:
                    # ⚠️ 净身后再转发：模型思考里常有英文/代码，不能漏给前端
                    yield thinking_event(text, phase="extract")
                    continue
                full_text += text
                yield {"event": "extract_delta", "text": text}
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
            await gen.release_llm(llm, owns=True)
        return
    except Exception as e:  # noqa: BLE001
        yield {"event": "error", "message": describe_llm_error(e)}
        if owns_client:
            await gen.release_llm(llm, owns=True)
        return

    if not extracted:
        yield {"event": "done", "saved_count": 0, "provider": provider, "model": model}
        if owns_client:
            await gen.release_llm(llm, owns=True)
        return

    yield {"event": "extract_done", "characters": extracted}

    # Step 2: 并行流式生成每张卡；每个 card 用 queue 透出事件
    yield {"event": "phase", "phase": "cards"}

    # ⚠️ **写库必须串行**（见模块 docstring）。
    db_lock = asyncio.Lock()

    async def card_runner(item: dict[str, str]) -> CardQueueHandle:
        """单卡流式生成 → 解析 → 入库。"""
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def produce() -> None:
            try:
                await q.put({"event": "card_start", "name": item["name"], "role": item["role"]})
                full_text = ""
                splitter = ThinkSplitter()
                stream = await llm.chat(
                    [
                        ChatMessage(
                            "user",
                            _build_card_prompt(
                                name=item["name"],
                                role=item["role"],
                                genre=genre,
                                outline=outline,
                                user_extra=user_extra,
                                load_prompt=load_prompt,
                            ),
                        )
                    ],
                    temperature=0.7,
                    stream=True,
                )
                async for delta in stream:
                    if not delta:
                        continue
                    for kind, text in splitter.feed(delta):
                        if kind == KIND_THINK:
                            await q.put(
                                thinking_event(
                                    text,
                                    phase="card",
                                    name=item["name"],
                                )
                            )
                            continue
                        full_text += text
                        await q.put(
                            {
                                "event": "card_delta",
                                "name": item["name"],
                                "text": text,
                            }
                        )
                # 解析 + 入库
                cleaned = strip_thinking(full_text)
                # 自动调用 scene=character_generation 的 post-process skills
                post_cleaned = await skill_manager.apply_post("character_generation", cleaned)
                data = extract_yaml_block(post_cleaned)
                from ..schemas.character import CharacterCreate

                # 入库串行（见上面 db_lock 的说明）：共用一个 AsyncSession 不能并发写
                async with db_lock:
                    character = await char_service.create(
                        CharacterCreate(
                            novel_id=novel_id,
                            name=item["name"],
                            role=item["role"],
                            basic_info=_trim_to_str(data.get("basic_info")),
                            personality=_trim_to_str(data.get("personality")),
                            habits=_trim_to_str(data.get("habits")),
                            thinking=_trim_to_str(data.get("thinking")),
                            relationships=_trim_to_str(data.get("relationships")),
                            growth_arc=_trim_to_str(data.get("growth_arc")),
                        )
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
        return CardQueueHandle(name=item["name"], q=q, task=task)

    handles = [await card_runner(item) for item in extracted]
    # saved_count 按**实际存进去的张数**算（失败的卡不能算）
    saved_count = 0
    try:
        async for payload in merge_queue_events([h.q for h in handles]):
            if payload.get("event") == "card_done":
                saved_count += 1
            yield payload
    finally:
        await asyncio.gather(*(h.task for h in handles), return_exceptions=True)
        if owns_client:
            await gen.release_llm(llm, owns=True)

    yield {
        "event": "done",
        "saved_count": saved_count,
        "provider": provider,
        "model": model,
        # 耗时（用户明确要求："添加生成当前模型耗时多少秒"）
        "elapsed_sec": round(time.monotonic() - t0, 2),
    }
