"""AI 辅助续写大纲单元测试（2026-10-25 新增）。

覆盖：
- 新卷**追加**到原大纲末尾（原有内容不动）
- 续写时把"已有大纲 + 已写章节"喂给模型（否则接不上剧情）
- 原大纲在 DB 里被更新
- 大纲不存在 → 404（端点前置校验）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.models.outline import OUTLINE_TYPES
from src.services.outline_continuation import (
    OutlineContinuationService,
    _average_chapters_per_volume,
    _build_existing_context,
)


class _ScriptedLLM:
    """按调用顺序返回预设内容的假 LLM。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[list[ChatMessage]] = []

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
        content = self.responses[index] if index < len(self.responses) else "{}"
        if not stream:
            return ChatResponse(content=content, model=self.model)

        async def _gen():
            for i in range(0, len(content), 30):
                yield content[i : i + 30]

        return _gen()


_SKELETON = json.dumps(
    {
        "volumes": [
            {
                "name": "第三卷 追杀",
                "summary": "宿敌卷土重来。",
                "chapters": [{"title": "第三卷 第一章"}, {"title": "第三卷 第二章"}],
            }
        ],
        "overall_theme": "主题",
    },
    ensure_ascii=False,
)

_DETAIL = json.dumps(
    {
        "chapters": [
            {"summary": "概要1", "key_events": ["事件1"]},
            {"summary": "概要2", "key_events": ["事件2"]},
        ]
    },
    ensure_ascii=False,
)


async def _seed_novel_with_outline(session: Any, *, chapters: int = 2) -> tuple[int, int]:
    """建一个作品 + 两卷大纲，返回 ``(novel_id, outline_id)``。"""
    from src.db import SessionLocal
    from src.models.novel import Novel
    from src.models.outline import Outline

    async with SessionLocal() as s:
        novel = Novel(name="续写测试", genre="修仙", description="主角逆袭的故事。")
        s.add(novel)
        await s.flush()
        await s.refresh(novel)
        outline = Outline(
            novel_id=novel.id,
            outline_type="complete",
            structure={
                "volumes": [
                    {
                        "name": "第一卷 觉醒",
                        "summary": "主角觉醒。",
                        "chapters": [{"title": "第一章 变故"}, {"title": "第二章 测试"}],
                    },
                    {
                        "name": "第二卷 崛起",
                        "summary": "开始修行。",
                        "chapters": [{"title": "第三章 入宗"}],
                    },
                ],
                "overall_theme": "凡人修仙",
            },
        )
        s.add(outline)
        await s.commit()
        await s.refresh(outline)
        novel_id, outline_id = novel.id, outline.id

    # 已写章节（续写时要读）
    from src.db import SessionLocal
    from src.models.chapter import Chapter, ChapterVersion

    async with SessionLocal() as s:
        for i in range(chapters):
            chapter = Chapter(
                novel_id=novel_id,
                chapter_number=i + 1,
                title=f"第{i + 1}章 已写",
                word_count=1200,
                status="written",
                outline=f"第{i + 1}章概要",
            )
            s.add(chapter)
            await s.flush()
            version = ChapterVersion(
                chapter_id=chapter.id,
                content=f"第 {i + 1} 章正文开头……",
                trigger="llm_generate",
                word_count=1200,
            )
            s.add(version)
            await s.flush()
            await s.refresh(version)
            chapter.current_version_id = version.id
        await s.commit()
    return novel_id, outline_id


# ===== 纯函数 =====


def test_average_chapters_per_volume() -> None:
    assert _average_chapters_per_volume([{"chapters": [1, 2]}, {"chapters": [3]}]) == 2
    assert _average_chapters_per_volume([]) == 10


def test_build_existing_context_lists_volumes_and_chapters() -> None:
    text = _build_existing_context(
        [{"name": "第一卷", "summary": "概要", "chapters": [{"title": "第一章"}]}]
    )
    assert "第一卷" in text
    assert "概要" in text
    assert "第一章" in text


def test_continue_type_is_supported() -> None:
    assert "complete" in OUTLINE_TYPES
    assert "semi_open" in OUTLINE_TYPES


# ===== 端到端 =====


@pytest.mark.asyncio
async def test_continue_appends_new_volumes(db_initialized: Path) -> None:
    """新卷追加到原大纲末尾，原有两卷不动。"""
    from src.db import SessionLocal
    from src.models.outline import Outline

    novel_id, outline_id = await _seed_novel_with_outline(SessionLocal)
    llm = _ScriptedLLM([_SKELETON, _DETAIL])

    async with SessionLocal() as session:
        service = OutlineContinuationService(session, llm_client=llm)
        events = [
            ev
            async for ev in service.stream_continue(
                novel_id, outline_id, volume_count=1, chapters_per_volume=2
            )
        ]

    done = [e for e in events if e["event"] == "done"]
    assert done, "应该有 done 事件"
    structure = done[0]["structure"]
    assert len(structure["volumes"]) == 3
    assert structure["volumes"][0]["name"] == "第一卷 觉醒"
    assert structure["volumes"][2]["name"] == "第三卷 追杀"
    # 细节阶段补上的概要
    assert structure["volumes"][2]["chapters"][0]["summary"] == "概要1"

    # DB 里的大纲也被更新了
    async with SessionLocal() as session:
        outline = await session.get(Outline, outline_id)
        assert outline is not None
        assert len(outline.structure["volumes"]) == 3


@pytest.mark.asyncio
async def test_continue_prompt_contains_existing_and_written_context(
    db_initialized: Path,
) -> None:
    """续写 prompt 必须带上已有大纲和已写章节（否则接不上剧情）。"""
    from src.db import SessionLocal

    novel_id, outline_id = await _seed_novel_with_outline(SessionLocal)
    llm = _ScriptedLLM([_SKELETON, _DETAIL])

    async with SessionLocal() as session:
        service = OutlineContinuationService(session, llm_client=llm)
        async for _ in service.stream_continue(
            novel_id, outline_id, volume_count=1, chapters_per_volume=2
        ):
            pass

    skeleton_prompt = llm.calls[0][0].content
    assert "第一卷 觉醒" in skeleton_prompt
    assert "第二卷 崛起" in skeleton_prompt
    assert "已写" in skeleton_prompt


@pytest.mark.asyncio
async def test_continue_on_missing_outline_yields_error(db_initialized: Path) -> None:
    """大纲不存在 → 流内 error 事件（不抛异常崩掉流）。"""
    from src.db import SessionLocal

    llm = _ScriptedLLM([_SKELETON])
    async with SessionLocal() as session:
        service = OutlineContinuationService(session, llm_client=llm)
        events = [ev async for ev in service.stream_continue(1, 999999)]
    assert events[0]["event"] == "error"


@pytest.mark.asyncio
async def test_continue_api_returns_404_for_missing_outline(db_initialized: Path) -> None:
    """端点前置校验：不存在的大纲直接 404（不是流内错误）。"""
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/novels/1/outlines/999999/continue/stream",
            json={"volume_count": 1},
        )
    assert resp.status_code == 404
