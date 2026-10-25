"""两阶段大纲生成单元测试（2026-10-25 新增）。

覆盖：
- ``sanitize_skeleton``：字段白名单、丢掉没标题的章节、丢掉空卷
- ``merge_volume_details``：按下标合并细节，失败的卷保留骨架原样
- ``TwoPhaseOutlineBuilder``：阶段一产骨架、阶段二各卷并行、单卷失败不拖垮整体
- 规模参数真的写进了 prompt（这是"想法被无视"的根治点）
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.core.outline_scale import normalize_scale
from src.services.outline_two_phase import (
    TwoPhaseOutlineBuilder,
    TwoPhaseOutlineError,
    merge_volume_details,
    sanitize_skeleton,
)

# ===== 假 LLM =====


class _ScriptedLLM:
    """按调用顺序返回预设内容的假 LLM（支持流式）。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, responses: list[str], *, fail_indices: set[int] | None = None) -> None:
        self.responses = responses
        self.fail_indices = fail_indices or set()
        self.calls: list[list[ChatMessage]] = []
        self.max_concurrent = 0
        self._active = 0

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        index = len(self.calls)
        self.calls.append(messages)
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            # 让并发真正重叠（否则测不出"并行"）
            await asyncio.sleep(0.01)
            if index in self.fail_indices:
                raise RuntimeError(f"boom {index}")
            content = self.responses[index] if index < len(self.responses) else "{}"
            if not stream:
                return ChatResponse(content=content, model=self.model)

            async def _gen():
                for i in range(0, len(content), 30):
                    yield content[i : i + 30]

            return _gen()
        finally:
            self._active -= 1


def _skeleton_json(volumes: int = 2, chapters: int = 3) -> str:
    data = {
        "volumes": [
            {
                "name": f"第{i + 1}卷 测试",
                "summary": f"第{i + 1}卷概要。",
                "chapters": [{"title": f"第{i + 1}卷 第{j + 1}章"} for j in range(chapters)],
            }
            for i in range(volumes)
        ],
        "overall_theme": "主题",
    }
    return json.dumps(data, ensure_ascii=False)


def _detail_json(chapters: int = 3) -> str:
    data = {
        "chapters": [
            {
                "summary": f"第{j + 1}章概要。",
                "key_events": [f"事件{j + 1}a", f"事件{j + 1}b"],
            }
            for j in range(chapters)
        ]
    }
    return json.dumps(data, ensure_ascii=False)


# ===== sanitize_skeleton =====


def test_sanitize_strips_unknown_top_level_fields() -> None:
    out = sanitize_skeleton(
        {
            "volumes": [{"name": "第一卷", "chapters": [{"title": "第一章"}]}],
            "unexpected": "脏字段",
        }
    )
    assert "unexpected" not in out
    assert out["volumes"][0]["name"] == "第一卷"


def test_sanitize_drops_chapters_without_title() -> None:
    out = sanitize_skeleton(
        {"volumes": [{"name": "第一卷", "chapters": [{"title": ""}, {"title": "第一章"}]}]}
    )
    assert len(out["volumes"][0]["chapters"]) == 1
    assert out["volumes"][0]["chapters"][0]["title"] == "第一章"


def test_sanitize_drops_empty_volumes() -> None:
    out = sanitize_skeleton(
        {
            "volumes": [
                {"name": "空卷", "chapters": []},
                {"name": "第一卷", "chapters": [{"title": "A"}]},
            ]
        }
    )
    assert len(out["volumes"]) == 1


def test_sanitize_keeps_suspense_hook_only_for_semi_open() -> None:
    raw = {"volumes": [{"name": "第一卷", "chapters": [{"title": "A"}]}], "suspense_hook": "钩子"}
    assert "suspense_hook" in sanitize_skeleton(raw, outline_type="semi_open")
    assert "suspense_hook" not in sanitize_skeleton(raw, outline_type="complete")


# ===== merge_volume_details =====


def test_merge_details_uses_skeleton_for_missing_volume() -> None:
    skeleton = {
        "volumes": [
            {"name": "第一卷", "chapters": [{"title": "A"}]},
            {"name": "第二卷", "chapters": [{"title": "B"}]},
        ]
    }
    merged = merge_volume_details(
        skeleton, {0: {"chapters": [{"summary": "概要A", "key_events": ["x"]}]}}
    )
    assert merged["volumes"][0]["chapters"][0]["summary"] == "概要A"
    assert merged["volumes"][0]["chapters"][0]["key_events"] == ["x"]
    # 第二卷没补上 → 保留骨架原样
    assert merged["volumes"][1]["chapters"][0]["title"] == "B"
    assert "summary" not in merged["volumes"][1]["chapters"][0]


def test_merge_details_keeps_title_from_skeleton() -> None:
    """细节阶段不能改标题（标题在阶段一就定了）。"""
    skeleton = {"volumes": [{"name": "第一卷", "chapters": [{"title": "原标题"}]}]}
    merged = merge_volume_details(
        skeleton,
        {0: {"chapters": [{"title": "被改的标题", "summary": "概要"}]}},
    )
    assert merged["volumes"][0]["chapters"][0]["title"] == "原标题"


# ===== TwoPhaseOutlineBuilder =====


@pytest.mark.asyncio
async def test_builder_emits_skeleton_then_volume_done() -> None:
    llm = _ScriptedLLM([_skeleton_json(2, 3), _detail_json(3), _detail_json(3)])
    builder = TwoPhaseOutlineBuilder(
        llm,
        genre="修仙",
        plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
        scale=normalize_scale(6, 3, 3000),
        outline_type="complete",
    )
    events = [ev async for ev in builder.run()]
    kinds = [ev["event"] for ev in events]

    assert "skeleton" in kinds
    assert kinds.count("volume_done") == 2
    assert kinds[-1] == "structure_ready"

    structure = events[-1]["structure"]
    assert len(structure["volumes"]) == 2
    assert structure["volumes"][0]["chapters"][0]["key_events"] == ["事件1a", "事件1b"]


@pytest.mark.asyncio
async def test_builder_details_run_in_parallel() -> None:
    """各卷并行（总耗时 ≈ 最慢的那一卷，而不是各卷之和）。"""
    llm = _ScriptedLLM(
        [_skeleton_json(4, 2), _detail_json(2), _detail_json(2), _detail_json(2), _detail_json(2)]
    )
    builder = TwoPhaseOutlineBuilder(
        llm,
        genre="修仙",
        plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
        scale=normalize_scale(8, 2, 3000),
        outline_type="complete",
    )
    async for _ in builder.run():
        pass
    assert llm.max_concurrent > 1, "各卷的细节应该并行调用"


@pytest.mark.asyncio
async def test_builder_single_volume_failure_does_not_kill_run() -> None:
    """单卷失败 → 只报 volume_error，其余卷照常，整体结构仍产出。"""
    llm = _ScriptedLLM(
        [_skeleton_json(2, 2), _detail_json(2), _detail_json(2)],
        fail_indices={1},
    )
    builder = TwoPhaseOutlineBuilder(
        llm,
        genre="修仙",
        plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
        scale=normalize_scale(4, 2, 3000),
        outline_type="complete",
    )
    events = [ev async for ev in builder.run()]
    kinds = [ev["event"] for ev in events]
    assert "volume_error" in kinds
    assert "volume_done" in kinds
    assert kinds[-1] == "structure_ready"
    structure = events[-1]["structure"]
    assert len(structure["volumes"]) == 2


@pytest.mark.asyncio
async def test_builder_writes_scale_into_prompt() -> None:
    """规模参数必须出现在 prompt 里 —— 这是"想法被无视"的根治点。"""
    llm = _ScriptedLLM([_skeleton_json(1, 2), _detail_json(2)])
    builder = TwoPhaseOutlineBuilder(
        llm,
        genre="修仙",
        plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
        keywords=["废柴", "逆袭"],
        scale=normalize_scale(100, 10, 3000),
        outline_type="complete",
        user_extra="不要系统流",
    )
    async for _ in builder.run():
        pass
    skeleton_prompt = llm.calls[0][0].content
    assert "100" in skeleton_prompt
    assert "3000" in skeleton_prompt
    assert "不要系统流" in skeleton_prompt
    # 细节 prompt 里带上本卷的章节骨架
    detail_prompt = llm.calls[1][0].content
    assert "第1卷 第1章" in detail_prompt


@pytest.mark.asyncio
async def test_builder_raises_when_skeleton_is_empty() -> None:
    llm = _ScriptedLLM(['{"summary": "没有卷"}'])
    builder = TwoPhaseOutlineBuilder(
        llm,
        genre="修仙",
        plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
        scale=normalize_scale(10, 5, 3000),
        outline_type="complete",
    )
    with pytest.raises(TwoPhaseOutlineError):
        async for _ in builder.run():
            pass
