"""QualityService 单元测试 (Phase 5.2/5.3/5.4)。

覆盖：
- 5 维度 prompt 加载
- format_characters_for_quality / load_genre_rules
- _extract_json: 普通 JSON / markdown 包 JSON / thinking 块 / 非 JSON
- _parse_dimension_response: 正常 / score 越界 / 缺字段
- QualityService.check_chapter: 5 维度并行 / LLM 失败容忍 / 总分计算
- API: POST /novels/{id}/chapters/{cid}/quality
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.core.quality.prompts import (
    QUALITY_DIMENSIONS,
    QualityPromptError,
    format_characters_for_quality,
    load_genre_rules,
    load_quality_prompt,
)
from src.services.quality_service import (
    QualityCheckError,
    # ⚠️ 必须写在**模块顶层**（AGENTS.md §7.3）：conftest 的 temp_db fixture 会
    #    重建 src.* 模块，函数体 import 拿到的是**新类**，pytest.raises 永远不匹配。
    QualityNotFoundError,
    QualityService,
)

# ===== prompt 加载 =====


def test_load_all_5_prompts() -> None:
    for dim in QUALITY_DIMENSIONS:
        p = load_quality_prompt(dim)
        assert isinstance(p, str)
        assert "{chapter_content}" in p or "{genre}" in p


def test_load_unknown_dimension() -> None:
    with pytest.raises(QualityPromptError):
        load_quality_prompt("nope")


# ===== format_characters / load_genre_rules =====


def test_format_characters_for_quality_empty() -> None:
    assert "暂无人物卡" in format_characters_for_quality([])


def test_format_characters_for_quality_basic() -> None:
    from src.models.character import Character

    c = Character(
        id=1,
        novel_id=1,
        name="韩立",
        role="主角",
        personality="谨慎",
        habits="动手前先想",
    )
    out = format_characters_for_quality([c])
    assert "韩立" in out
    assert "谨慎" in out


def test_load_genre_rules_xiuxian() -> None:
    text = load_genre_rules("xiuxian")
    assert "修仙" in text or "等级" in text or "灵根" in text or "境界" in text


def test_load_genre_rules_unknown_fallback() -> None:
    text = load_genre_rules("不存在的题材")
    assert "暂无" in text or "无" in text


def test_load_genre_rules_empty() -> None:
    assert "未指定" in load_genre_rules("")


# ===== _extract_json =====


def test_extract_json_plain() -> None:
    obj = QualityService._extract_json('{"a": 1, "b": [2, 3]}')
    assert obj == {"a": 1, "b": [2, 3]}


def test_extract_json_in_markdown() -> None:
    text = '```json\n{"score": 7.5, "issues": []}\n```'
    obj = QualityService._extract_json(text)
    assert obj["score"] == 7.5


def test_extract_json_strip_thinking() -> None:
    text = '<think>分析中...</think>\n```json\n{"score": 8.0}\n```'
    obj = QualityService._extract_json(text)
    assert obj["score"] == 8.0


def test_extract_json_no_json_raises() -> None:
    with pytest.raises(ValueError):
        QualityService._extract_json("plain text no json")


def test_extract_json_unclosed_raises() -> None:
    with pytest.raises(ValueError):
        QualityService._extract_json('{"a": 1')


# ===== _parse_dimension_response =====


def test_parse_dimension_normal() -> None:
    raw = '{"score": 7.5, "issues": [{"type": "流畅", "quote": "x", "problem": "p", "suggestion": "s"}], "suggestions": ["全局建议"]}'
    r = QualityService._parse_dimension_response("writing", raw)
    assert r.dimension == "writing"
    assert r.score == 7.5
    assert r.error is None
    assert len(r.issues) == 1
    assert r.issues[0].type == "流畅"
    assert r.suggestions == ["全局建议"]


def test_parse_dimension_score_clamped() -> None:
    raw = '{"score": 99.0}'
    r = QualityService._parse_dimension_response("writing", raw)
    assert r.score == 10.0  # clamp 到 10


def test_parse_dimension_score_negative_clamped() -> None:
    raw = '{"score": -1.0}'
    r = QualityService._parse_dimension_response("writing", raw)
    assert r.score == 0.0


def test_parse_dimension_missing_fields() -> None:
    r = QualityService._parse_dimension_response("writing", "{}")
    assert r.score == 0.0
    assert r.issues == []


def test_parse_dimension_empty() -> None:
    r = QualityService._parse_dimension_response("writing", "")
    assert r.error is not None
    assert r.score == 0.0


def test_parse_dimension_invalid_json() -> None:
    r = QualityService._parse_dimension_response("writing", "not json")
    assert r.error is not None


def test_parse_dimension_consistency_with_character() -> None:
    raw = '{"score": 8.0, "issues": [{"character": "韩立", "quote": "y", "problem": "p", "suggestion": "s"}]}'
    r = QualityService._parse_dimension_response("consistency", raw)
    assert r.issues[0].character == "韩立"


# ===== QualityService.check_chapter =====


def _mock_llm_responses(per_dim: dict[str, str] | None = None) -> AsyncMock:
    """默认所有维度返回 score=7.0 + 1 issue；可指定 per_dim 覆盖。"""

    async def fake_chat(messages: list[ChatMessage], **_kw: object) -> ChatResponse:
        # 通过 prompt 内容粗略识别当前维度（"## 任务" 之后第一行含维度名）
        text = messages[0].content
        dim = "writing"
        for d in QUALITY_DIMENSIONS:
            if d in text[:200].lower() or d in text[:300]:
                dim = d
                break
        content = (per_dim or {}).get(
            dim, '{"score": 7.0, "issues": [], "suggestions": ["建议 A"]}'
        )
        return ChatResponse(content=content, model="mock")

    m = AsyncMock()
    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock-model"
    m.aclose = AsyncMock()
    return m


async def _make_chapter(db_initialized: Path) -> tuple[int, int]:
    """最小数据集：novel + 1 character + 1 chapter (with content)。"""
    from src.db import SessionLocal
    from src.models.chapter import Chapter, ChapterVersion
    from src.models.character import Character
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xiuxian"))
        ch = Chapter(novel_id=novel.id, chapter_number=1, title="第一章", status="drafting")
        session.add(ch)
        await session.flush()
        ver = ChapterVersion(
            chapter_id=ch.id, content="韩立提剑冲上去。", trigger="user_create", word_count=10
        )
        session.add(ver)
        await session.flush()
        ch.current_version_id = ver.id
        c = Character(
            novel_id=novel.id,
            name="韩立",
            role="主角",
            personality="谨慎",
        )
        session.add(c)
        await session.commit()
        return novel.id, ch.id


@pytest.mark.asyncio
async def test_check_chapter_5_dimensions_parallel(db_initialized: Path) -> None:
    novel_id, chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses())
        report = await svc.check_chapter(novel_id, chapter_id)
    assert report.chapter_id == chapter_id
    assert report.novel_id == novel_id
    assert set(report.dimension_scores.keys()) == set(QUALITY_DIMENSIONS)
    # 总分 = 5 个 7.0 均分 = 7.0
    assert report.total_score == 7.0
    assert report.provider == "mock"
    # 5 个维度 result
    assert len(report.dimension_results) == 5
    # 5 维度各 1 个建议（合并后 5 个）
    assert len(report.suggestions) == 5


@pytest.mark.asyncio
async def test_check_chapter_dimension_failure_tolerated(db_initialized: Path) -> None:
    """某个维度 LLM 失败：返回 error，不影响其他维度。"""
    novel_id, chapter_id = await _make_chapter(db_initialized)

    # 让 writing 维度返回无效 JSON（其他维度正常）
    per_dim = {"writing": "not json at all"}
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses(per_dim))
        report = await svc.check_chapter(novel_id, chapter_id)
    # writing 维度 error，但其他 4 维度 OK
    writing_result = next(r for r in report.dimension_results if r.dimension == "writing")
    assert writing_result.error is not None
    assert report.dimension_scores["writing"] == 0.0
    # 总分 = 4 个 7.0 均分 = 7.0（writing 不计入）
    assert report.total_score == 7.0


@pytest.mark.asyncio
async def test_check_chapter_empty_content_raises(db_initialized: Path) -> None:
    from src.db import SessionLocal
    from src.models.chapter import Chapter
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xiuxian"))
        ch = Chapter(novel_id=novel.id, chapter_number=1, title="空章节", status="outline")
        session.add(ch)
        await session.commit()
        ch_id = ch.id
        novel_id = novel.id

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses())
        with pytest.raises(QualityCheckError, match="no content"):
            await svc.check_chapter(novel_id, ch_id)


@pytest.mark.asyncio
async def test_check_chapter_not_found(db_initialized: Path) -> None:
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses())
        with pytest.raises(QualityCheckError, match="not found"):
            await svc.check_chapter(novel_id=1, chapter_id=9999)


@pytest.mark.asyncio
async def test_check_chapter_wrong_novel(db_initialized: Path) -> None:
    """chapter 不属于 novel_id：抛 QualityCheckError。"""
    novel_id, chapter_id = await _make_chapter(db_initialized)
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses())
        with pytest.raises(QualityCheckError, match="not in novel"):
            await svc.check_chapter(novel_id=9999, chapter_id=chapter_id)


# ===== API 端点 =====


@pytest.mark.asyncio
async def test_api_quality_check(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.main import app

    novel_id, chapter_id = await _make_chapter(db_initialized)
    client = TestClient(app)
    # 注入 mock LLM：通过 dependency override
    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.api.quality import get_service
    from src.db import get_db
    from src.services.quality_service import QualityService

    async def _override(
        session: AsyncSession = Depends(get_db),  # noqa: B008
    ) -> QualityService:
        return QualityService(session, llm_client=_mock_llm_responses())

    app.dependency_overrides[get_service] = _override
    try:
        resp = client.post(f"/novels/{novel_id}/chapters/{chapter_id}/quality")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, f"got {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["chapter_id"] == chapter_id
    assert body["novel_id"] == novel_id
    assert body["total_score"] == 7.0
    assert set(body["dimension_scores"].keys()) == set(QUALITY_DIMENSIONS)
    assert len(body["dimension_results"]) == 5


@pytest.mark.asyncio
async def test_api_quality_check_chapter_not_found(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xiuxian"))
        novel_id = novel.id

    client = TestClient(app)
    resp = client.post(f"/novels/{novel_id}/chapters/9999/quality")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_quality_check_empty_chapter_422(db_initialized: Path) -> None:
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.models.chapter import Chapter
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xiuxian"))
        ch = Chapter(novel_id=novel.id, chapter_number=1, title="空", status="outline")
        session.add(ch)
        await session.commit()
        novel_id = novel.id
        ch_id = ch.id

    client = TestClient(app)
    resp = client.post(f"/novels/{novel_id}/chapters/{ch_id}/quality")
    assert resp.status_code == 422
    assert "no content" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_quality_not_found_is_typed_error(db_initialized: Path) -> None:
    """不存在 → 抛 ``QualityNotFoundError``（**类型**判定，不是字符串匹配）。

    ⚠️ 2026-10-25 巡检：API 层原来靠 ``"not found" in msg.lower()`` 判 404，
    字符串匹配会被**内容**误伤。现在用专门的子类。
    """
    from src.db import SessionLocal

    async with SessionLocal() as session:
        svc = QualityService(session, llm_client=_mock_llm_responses())
        with pytest.raises(QualityNotFoundError):
            await svc.check_chapter(novel_id=1, chapter_id=9999)
        # 仍是 QualityCheckError 的子类，老代码不受影响
        assert issubclass(QualityNotFoundError, QualityCheckError)


@pytest.mark.asyncio
async def test_api_quality_stream_chapter_not_found_returns_404(db_initialized: Path) -> None:
    """流式端点：章节不存在 → **开流之前**就 404。

    ⚠️ 原来没有前置校验，异常在 generator 里抛 → 客户端收到一段被截断的
    200 响应 → 既没 error 帧也没 done 帧 → 前端界面永远转圈（§4.10）。
    """
    from fastapi.testclient import TestClient

    from src.db import SessionLocal
    from src.main import app
    from src.schemas.novel import NovelCreate
    from src.services.novel_service import NovelService

    async with SessionLocal() as session:
        novel = await NovelService(session).create(NovelCreate(name="测试", genre="xiuxian"))
        novel_id = novel.id

    client = TestClient(app)
    resp = client.post(f"/novels/{novel_id}/chapters/9999/quality/stream")
    assert resp.status_code == 404
