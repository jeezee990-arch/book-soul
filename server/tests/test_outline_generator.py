"""OutlineGenerator 单元测试（Phase 3.4）。

覆盖：
- generate() complete 模式：入库 + 返回 novel/outline
- generate() freedom 模式：JSON 形状不同也通过
- _upsert_novel 同名不重复创建
- _upsert_novel 新建
- generate() 同 type 重复生成 → 删除旧的后再创（覆盖语义）
- generate() LLM 抛异常 → OutlineGenerationError
- generate() LLM 返回非 JSON → OutlineGenerationError
- _load_outline_prompt 缓存 + 缺失文件
- strip_thinking / extract_json_object 辅助函数
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from loguru import logger

from src.core.llm.base import ChatMessage, ChatResponse
from src.services.outline_generator import (
    OutlineGenerationError,
    OutlineGenerator,
    _load_outline_prompt,
)


@pytest.fixture
def mock_llm_complete() -> AsyncMock:
    """返回合法 complete JSON 的 mock LLM。"""
    fake_json = """{
        "volumes": [
            {
                "name": "第一卷 觉醒",
                "summary": "主角觉醒血脉。",
                "chapters": [
                    {
                        "title": "第一章 变故",
                        "summary": "家族被灭。",
                        "key_events": ["夜袭", "逃生"]
                    },
                    {
                        "title": "第二章 测试",
                        "summary": "灵根测试。",
                        "key_events": ["测试灵根"]
                    }
                ]
            }
        ],
        "overall_theme": "凡人修仙"
    }"""

    async def fake_chat(_m: list[ChatMessage], **_kw: object) -> ChatResponse:
        return ChatResponse(content=fake_json, model="mock")

    m = AsyncMock()
    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    return m


@pytest.fixture
def mock_llm_freedom() -> AsyncMock:
    fake_json = """{
        "summary": "整体故事梗概。一个凡人修仙的热血故事。",
        "key_beats": ["开端：灵根测试", "发展：拜入宗门", "高潮：突破筑基", "收束：飞升成仙"],
        "themes": ["逆天改命", "长生"]
    }"""

    async def fake_chat(_m: list[ChatMessage], **_kw: object) -> ChatResponse:
        return ChatResponse(content=fake_json, model="mock")

    m = AsyncMock()
    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    return m


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    import importlib

    import src.services.outline_generator as _og

    importlib.reload(_og)
    _og.OutlineGenerator.clear_prompt_cache()
    globals()["OutlineGenerator"] = _og.OutlineGenerator
    globals()["OutlineGenerationError"] = _og.OutlineGenerationError
    globals()["_load_outline_prompt"] = _og._load_outline_prompt
    yield
    _og.OutlineGenerator.clear_prompt_cache()


# ===== _load_outline_prompt =====


def test_load_outline_prompt_returns_str() -> None:
    # ⚠️ 2026-10-25 起 complete / semi_open 走**两阶段**模板
    #    （outline_skeleton.yaml + outline_volume_detail.yaml），
    #    只有 freedom 还是单阶段模板。
    for t in ("freedom",):
        p = _load_outline_prompt(t)
        assert isinstance(p, str)
        assert "{genre}" in p
        assert "{plot}" in p


def test_two_phase_prompt_templates_exist() -> None:
    """两阶段模板必须存在，且带齐规模参数占位符。"""
    from src.services.outline_two_phase import _load_phase_prompt

    skeleton = _load_phase_prompt("skeleton")
    for ph in ("{genre}", "{plot}", "{total_chapters}", "{volume_count}", "{volume_plan}"):
        assert ph in skeleton, f"骨架模板缺少占位符 {ph}"

    detail = _load_phase_prompt("volume_detail")
    for ph in ("{genre}", "{plot}", "{volume_index}", "{chapters_json}"):
        assert ph in detail, f"细节模板缺少占位符 {ph}"


def test_load_outline_prompt_missing_raises() -> None:
    with pytest.raises(OutlineGenerationError):
        _load_outline_prompt("nonexistent")


# ===== generate() complete 模式 =====


@pytest.mark.asyncio
async def test_generate_complete_creates_novel_and_outline(
    db_initialized: Path, mock_llm_complete: AsyncMock
) -> None:
    from src.db import SessionLocal
    from src.models.outline import Outline

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        result = await gen.generate(
            genre="修仙",
            plot_summary="主角是灵根被夺的废材，偶然获得传承逆袭。",
            keywords=["废柴", "逆袭"],
            novel_name="灵根重塑",
            outline_type="complete",
        )
    assert result["novel_name"] == "灵根重塑"
    assert result["outline_type"] == "complete"
    assert result["novel_id"] > 0
    assert result["outline_id"] > 0
    # 校验 structure 在 DB 里
    async with SessionLocal() as session:
        outline = await session.get(Outline, result["outline_id"])
        assert outline is not None
        assert outline.novel_id == result["novel_id"]
        vols = outline.structure["volumes"]
        assert len(vols) == 1
        assert vols[0]["name"] == "第一卷 觉醒"
        assert len(vols[0]["chapters"]) == 2


@pytest.mark.asyncio
async def test_generate_same_name_creates_new_novel(
    db_initialized: Path, mock_llm_complete: AsyncMock
) -> None:
    """同名再生成 → **新建一本**（名字自动加序号），不覆盖旧书。

    ⚠️ 2026-10-30 行为变更：以前这里按名字 upsert —— 名字撞上素材库里
    已有的一本书时，新书会被合并进旧书（旧书的大纲被冲掉），
    表现为"新书写不进素材库"。现在改成按 id 区分：不传 novel_id = 新建。
    """
    from sqlalchemy import func, select

    from src.db import SessionLocal
    from src.models.novel import Novel

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        r1 = await gen.generate(
            genre="修仙",
            plot_summary="第一次生成一段剧情内容。",
            novel_name="复用测试",
            outline_type="complete",
        )

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        r2 = await gen.generate(
            genre="修仙",
            plot_summary="第二次生成（不同 plot 的内容）。",
            novel_name="复用测试",  # 同名
            outline_type="complete",
        )

    # 两本不同的书
    assert r2["novel_id"] != r1["novel_id"]
    # 第二本自动加了序号
    assert r1["novel_name"] == "复用测试"
    assert r2["novel_name"] == "复用测试 2"

    # DB 里两本都还在（第一本没被覆盖掉）
    async with SessionLocal() as session:
        count = (
            await session.execute(select(func.count(Novel.id)).where(Novel.name == "复用测试"))
        ).scalar_one()
        assert count == 1
        count2 = (
            await session.execute(select(func.count(Novel.id)).where(Novel.name == "复用测试 2"))
        ).scalar_one()
        assert count2 == 1


@pytest.mark.asyncio
async def test_generate_reuses_novel_by_id(
    db_initialized: Path, mock_llm_complete: AsyncMock
) -> None:
    """传 novel_id → **复用同一本**（同一向导内重生成），同 type 覆盖旧大纲。"""
    from sqlalchemy import func, select

    from src.db import SessionLocal
    from src.models.outline import Outline

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        r1 = await gen.generate(
            genre="修仙",
            plot_summary="第一版剧情内容描述。",
            novel_name="覆盖测试",
            outline_type="complete",
        )

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        r2 = await gen.generate(
            genre="修仙",
            plot_summary="第二版剧情内容描述。",
            novel_id=r1["novel_id"],  # 复用同一本
            outline_type="complete",
        )

    # DB 里这个 novel 的 complete outline 只有 1 条（覆盖了）
    async with SessionLocal() as session:
        count = (
            await session.execute(
                select(func.count(Outline.id)).where(
                    Outline.novel_id == r2["novel_id"],
                    Outline.outline_type == "complete",
                )
            )
        ).scalar_one()
        assert count == 1
    # novel 仍是同一个
    assert r1["novel_id"] == r2["novel_id"]
    assert r1["novel_name"] == r2["novel_name"]


# ===== generate() freedom 模式 =====


@pytest.mark.asyncio
async def test_generate_freedom_works(db_initialized: Path, mock_llm_freedom: AsyncMock) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_freedom)
        result = await gen.generate(
            genre="修仙",
            plot_summary="一个凡人修仙的热血故事描述。",
            outline_type="freedom",
        )
    assert result["outline_type"] == "freedom"
    assert "summary" in result["structure"]
    assert "key_beats" in result["structure"]
    assert "themes" in result["structure"]
    assert isinstance(result["structure"]["key_beats"], list)


# ===== generate() 错误路径 =====


@pytest.mark.asyncio
async def test_generate_invalid_outline_type_raises(
    db_initialized: Path, mock_llm_complete: AsyncMock
) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        with pytest.raises(OutlineGenerationError) as exc_info:
            await gen.generate(
                genre="修仙",
                plot_summary="一些剧情内容描述。",
                outline_type="invalid_type",
            )
    assert "Invalid outline_type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_too_short_plot_raises(
    db_initialized: Path, mock_llm_complete: AsyncMock
) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=mock_llm_complete)
        with pytest.raises(OutlineGenerationError):
            await gen.generate(
                genre="修仙",
                plot_summary="太短",  # < 10
            )


@pytest.mark.asyncio
async def test_generate_llm_exception_wrapped(
    db_initialized: Path,
) -> None:
    from src.db import SessionLocal

    failing_llm = AsyncMock()
    failing_llm.chat = AsyncMock(side_effect=RuntimeError("network"))
    failing_llm.provider = "mock"

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=failing_llm)
        with pytest.raises(OutlineGenerationError) as exc_info:
            await gen.generate(
                genre="修仙",
                plot_summary="剧情足够长，描述完整具体。",
            )
    assert "network" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_llm_non_json_output_raises(db_initialized: Path) -> None:
    """LLM 返回非 JSON（无花括号）→ OutlineGenerationError。"""
    from src.db import SessionLocal

    bad_llm = AsyncMock()

    async def chat(_m: list[ChatMessage], **_kw: object) -> ChatResponse:
        return ChatResponse(content="这不是 JSON 啊", model="mock")

    bad_llm.chat = AsyncMock(side_effect=chat)
    bad_llm.provider = "mock"

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=bad_llm)
        with pytest.raises(OutlineGenerationError) as exc_info:
            await gen.generate(
                genre="修仙",
                plot_summary="剧情足够长，描述完整具体。",
            )
    assert "JSON" in str(exc_info.value) or "json" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_llm_invalid_structure_raises(db_initialized: Path) -> None:
    """LLM 返回合法 JSON 但 shape 不对（缺 volumes）→ OutlineGenerationError。"""
    from src.db import SessionLocal

    bad_shape_llm = AsyncMock()

    async def chat(_m: list[ChatMessage], **_kw: object) -> ChatResponse:
        return ChatResponse(content='{"summary": "缺少 volumes 字段"}', model="mock")

    bad_shape_llm.chat = AsyncMock(side_effect=chat)
    bad_shape_llm.provider = "mock"

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=bad_shape_llm)
        with pytest.raises(OutlineGenerationError) as exc_info:
            await gen.generate(
                genre="修仙",
                plot_summary="剧情足够长，描述完整具体。",
                outline_type="complete",  # 缺 volumes → 校验失败
            )
    assert "invalid" in str(exc_info.value).lower() or "structure" in str(exc_info.value).lower()


# ===== thinking 剥离（从 formatting.py 复用） =====


async def test_thinking_stripped_before_json_parse(db_initialized: Path) -> None:
    """端到端：LLM 输出含 <think> 块，service 应能正确解析。"""
    from src.db import SessionLocal

    thinking_llm = AsyncMock()

    async def chat(_m: list[ChatMessage], **_kw: object) -> ChatResponse:
        return ChatResponse(
            content="<think>让我想想。\n需要 volumes + chapters。</think>\n\n"
            '{"volumes":[{"name":"第一卷","chapters":[{"title":"第一章"}]}]}',
            model="mock",
        )

    thinking_llm.chat = AsyncMock(side_effect=chat)
    thinking_llm.provider = "mock"

    async with SessionLocal() as session:
        gen = OutlineGenerator(session, llm_client=thinking_llm)
        result = await gen.generate(
            genre="修仙",
            plot_summary="剧情足够长，描述完整具体。",
            outline_type="complete",
        )
    assert result["structure"]["volumes"][0]["name"] == "第一卷"


# 静默 logger 警告
logger.disable("src.services.outline_generator")
