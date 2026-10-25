"""大纲流式的"结构化增量"事件 + 半开放式大纲模式测试（2026-10-25 新增）。

覆盖两个用户反馈：

1. **大纲显示**：旧实现流式阶段把 LLM 吐的原始 JSON 用 ``<pre>`` 渲染 ——
   用户看到的是一堆英文代码。现在后端推 ``partial`` 事件（已解析好的结构），
   且**不再推** ``delta`` 事件（避免前端又去渲染裸 JSON）。

2. **两种大纲模式**：``complete``（写到全书结束）/ ``semi_open``（只写前期
   并留悬念，后续作者自行创作或 AI 辅助续写）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.models.outline import OUTLINE_TYPES
from src.services.outline_generator import OutlineGenerator, _load_outline_prompt


class _FakeStreamLLM:
    """按片段吐出内容的假 LLM（支持 ``stream=True``）。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        """非流式返回完整内容；流式返回逐片段的异步迭代器。"""
        if not stream:
            return ChatResponse(content="".join(self.chunks), model=self.model)

        async def _gen():
            for chunk in self.chunks:
                yield chunk

        return _gen()


def _complete_json_chunks() -> list[str]:
    """把一份完整大纲 JSON 切成若干片段（模拟流式吐字）。"""
    full = {
        "volumes": [
            {
                "name": "第一卷 觉醒",
                "summary": "主角觉醒血脉。",
                "chapters": [
                    {
                        "title": "第一章 变故",
                        "summary": "家族被灭。",
                        "key_events": ["夜袭", "逃生"],
                    },
                    {
                        "title": "第二章 测试",
                        "summary": "灵根测试。",
                        "key_events": ["测试灵根"],
                    },
                ],
            },
            {
                "name": "第二卷 崛起",
                "summary": "开始修行。",
                "chapters": [
                    {
                        "title": "第三章 入宗",
                        "summary": "拜入宗门。",
                        "key_events": ["拜师", "领功法"],
                    }
                ],
            },
        ],
        "overall_theme": "凡人修仙",
    }
    text = json.dumps(full, ensure_ascii=False)
    # 切成 40 字一段，模拟真实流式
    return [text[i : i + 40] for i in range(0, len(text), 40)]


# =====================================================================
# 流式协议：partial 事件（结构化增量）
# =====================================================================


@pytest.mark.asyncio
async def test_stream_emits_partial_structure_events(db_initialized: Path) -> None:
    """流式过程中要推 ``partial`` 事件，且内容是**已解析好的结构**。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(_complete_json_chunks())

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=llm)
        events = [
            ev
            async for ev in gen.stream_generate(
                genre="修仙",
                plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
                novel_name="流式测试",
                outline_type="complete",
            )
        ]

    partials = [e for e in events if e["event"] == "partial"]
    assert partials, "应该有 partial 事件（结构化增量），否则前端只能显示空白"

    # 最后一个 partial 应该包含全部章节
    last = partials[-1]
    assert last["chapters_done"] == 3
    volumes = last["structure"]["volumes"]
    assert len(volumes) == 2
    assert volumes[0]["name"] == "第一卷 觉醒"
    assert volumes[0]["chapters"][0]["key_events"] == ["夜袭", "逃生"]


@pytest.mark.asyncio
async def test_stream_does_not_emit_raw_delta_json(db_initialized: Path) -> None:
    """**不能**再推 ``delta`` 事件（那正是"显示代码"的根源）。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(_complete_json_chunks())

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=llm)
        events = [
            ev
            async for ev in gen.stream_generate(
                genre="修仙",
                plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
                novel_name="不推 delta 测试",
                outline_type="complete",
            )
        ]

    assert not [e for e in events if e["event"] == "delta"], (
        "不该再推 delta 事件 —— 前端会把原始 JSON 显示成代码"
    )


@pytest.mark.asyncio
async def test_stream_done_carries_model_and_timing(db_initialized: Path) -> None:
    """done 事件要带上模型名和耗时（用户要求显示"当前模型耗时多少秒"）。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(_complete_json_chunks())

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=llm)
        events = [
            ev
            async for ev in gen.stream_generate(
                genre="修仙",
                plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
                novel_name="耗时测试",
                outline_type="complete",
            )
        ]

    done = [e for e in events if e["event"] == "done"]
    assert done, "应该有 done 事件"
    assert done[0]["model"] == "mock-model"
    assert done[0]["provider"] == "mock"
    assert isinstance(done[0]["elapsed_sec"], (int, float))
    assert done[0]["elapsed_sec"] >= 0
    assert "first_delta_sec" in done[0]


@pytest.mark.asyncio
async def test_stream_thinking_event_is_forwarded(db_initialized: Path) -> None:
    """推理模型的思考内容要作为 ``thinking`` 事件转发（不能静默丢掉）。"""
    from src.db import SessionLocal

    llm = _FakeStreamLLM(["<think>先想一想</think>", *(_complete_json_chunks())])

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=llm)
        events = [
            ev
            async for ev in gen.stream_generate(
                genre="修仙",
                plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
                novel_name="思考测试",
                outline_type="complete",
            )
        ]

    thinking = [e for e in events if e["event"] == "thinking"]
    assert thinking, "应该有 thinking 事件"
    assert "先想一想" in thinking[0]["text"]


# =====================================================================
# 半开放式大纲（semi_open）
# =====================================================================


def test_semi_open_is_valid_outline_type() -> None:
    """semi_open 必须是被承认的大纲类型。"""
    assert "semi_open" in OUTLINE_TYPES


def test_semi_open_prompt_exists_and_mentions_suspense() -> None:
    """半开放式 prompt 要存在，且要明确要求"留悬念"。"""
    prompt = _load_outline_prompt("semi_open")
    assert "suspense_hook" in prompt
    assert "悬念" in prompt


@pytest.mark.asyncio
async def test_generate_semi_open_saves_structure(db_initialized: Path) -> None:
    """半开放式大纲能生成、入库，且保留悬念钩子。"""
    from src.db import SessionLocal
    from src.models.outline import Outline

    payload = {
        "volumes": [
            {
                "name": "第一卷 暗流",
                "summary": "主角发现父亲留下的账本。",
                "chapters": [
                    {
                        "title": "第一章 旧账本",
                        "summary": "整理遗物时翻出一本账本。",
                        "key_events": ["父亲下葬", "发现账本"],
                    }
                ],
            }
        ],
        "overall_theme": "有些真相，知道了就回不了头",
        "suspense_hook": "账本最后一页被撕掉的那一角，正好是父亲签名的位置。",
    }

    class _NonStreamLLM:
        provider = "mock"
        model = "mock-model"

        async def chat(self, *args: Any, **kwargs: Any) -> ChatResponse:
            return ChatResponse(content=json.dumps(payload, ensure_ascii=False), model=self.model)

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=_NonStreamLLM())
        result = await gen.generate(
            genre="悬疑",
            plot_summary="主角发现父亲留下的账本，牵出一桩旧案。",
            novel_name="半开放测试",
            outline_type="semi_open",
        )

    assert result["outline_type"] == "semi_open"
    assert result["structure"]["suspense_hook"].startswith("账本最后一页")

    async with SessionLocal() as session:
        outline = await session.get(Outline, result["outline_id"])
        assert outline is not None
        assert outline.outline_type == "semi_open"
        assert outline.structure["suspense_hook"]


@pytest.mark.asyncio
async def test_semi_open_rejects_unknown_fields(db_initialized: Path) -> None:
    """半开放式结构里有未知字段 → 校验失败（别让脏数据进库）。"""
    from src.db import SessionLocal

    payload = {
        "volumes": [],
        "overall_theme": "主题",
        "suspense_hook": "钩子",
        "unexpected_field": "不该出现",
    }

    class _BadLLM:
        provider = "mock"
        model = "mock-model"

        async def chat(self, *args: Any, **kwargs: Any) -> ChatResponse:
            return ChatResponse(content=json.dumps(payload, ensure_ascii=False), model=self.model)

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=_BadLLM())
        with pytest.raises(Exception) as exc_info:
            await gen.generate(
                genre="悬疑",
                plot_summary="剧情足够长，描述完整具体。",
                novel_name="脏数据测试",
                outline_type="semi_open",
            )
    assert "unexpected_field" in str(exc_info.value)
