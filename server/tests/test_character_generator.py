"""CharacterGenerator 单元测试（Phase 3.5）。

覆盖：
- _load_prompt 加载 extract_characters / generate_card
- _load_prompt 缺失 section 抛 CharacterGenerationError
- _normalize_role 容错（合法 + 非法 + 近义词）
- _trim_to_str 类型归一
- extract_json_array / extract_yaml_block（formatting 工具）
- generate_from_outline 正常路径：抽取 3 人物 → 3 张卡入库 + 初始版本
- generate_from_outline 空抽取 → 返回空 list
- generate_from_outline novel 不存在 → NovelNotFoundError
- generate_from_outline outline 非 dict → CharacterGenerationError
- generate_from_outline LLM 返回空 → CharacterGenerationError
- generate_from_outline LLM 返回非 JSON → CharacterGenerationError
- generate_from_outline 角色非法 → 归到"其他"
- generate_from_outline YAML 解析失败 → CharacterGenerationError
- generate_from_outline 角色名 / 主题 / 元信息透传
- stream_generate_from_outline 并发入库：多张卡必须**全部**入库（2026-10-24 回归）
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.core.llm.base import ChatMessage, ChatResponse
from src.services._character_helpers import (
    _normalize_role,
    _trim_to_str,
)
from src.services.character_generator import (
    CharacterGenerationError,
    CharacterGenerator,
    _load_prompt,
)
from src.services.character_service import NovelNotFoundError


def _session():
    """拿当前生效的 SessionLocal（不在模块顶部 import，避免绑死旧 engine）。"""
    from src.db import SessionLocal  # noqa: PLC0415

    return SessionLocal()


# ===== 测试 fixtures =====


_EXTRACT_JSON = """以下是 JSON：
```json
[
  {"name": "韩立", "role": "主角"},
  {"name": "南宫婉", "role": "主角团"},
  {"name": "墨大夫", "role": "反派"}
]
```"""

# step 2：每张卡的合法 YAML
_CARD_HANLI = """```yaml
basic_info: |
  凡人出身，资质平庸
personality: |
  谨慎、隐忍、务实
habits: |
  随身带多件保命法器
thinking: |
  凡事留后路
relationships: |
  道侣：南宫婉；师兄：厉飞雨
growth_arc: |
  从废材到飞升
```"""

_CARD_NANGONG = """```yaml
basic_info: |
  掩月宗长老
personality: |
  温柔中带坚定
habits: |
  喜欢种花
thinking: |
  重视情义
relationships: |
  道侣：韩立
growth_arc: |
  从宗派长老到双修伴侣
```"""

_CARD_MO = """```yaml
basic_info: |
  神秘炼药师
personality: |
  阴险狡诈
habits: |
  用毒
thinking: |
  为达目的不择手段
relationships: |
  与韩立为敌
growth_arc: |
  被识破后败亡
```"""


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """每个测试前后清 prompt lru_cache（不需要 reload，conftest 已隔离 DB）。"""
    import src.services.character_generator as _cg

    _cg.CharacterGenerator.clear_prompt_cache()
    yield
    _cg.CharacterGenerator.clear_prompt_cache()


def _make_mock_llm(
    extract_response: str = _EXTRACT_JSON,
    card_responses: dict[str, str] | None = None,
    fail_with: Exception | None = None,
    empty_response: bool = False,
) -> AsyncMock:
    """构造 mock LLM client。

    - 看到 step 1 关键词 → 返回 extract_response
    - step 2：根据 prompt 中"姓名：<name>"决定 card_responses 中的卡
    - fail_with 非 None → chat 抛该异常
    - empty_response=True → 返回空 content
    """
    if card_responses is None:
        card_responses = {
            "韩立": _CARD_HANLI,
            "南宫婉": _CARD_NANGONG,
            "墨大夫": _CARD_MO,
        }

    async def fake_chat(messages: list[ChatMessage], **_kw: object) -> ChatResponse:
        if fail_with is not None:
            raise fail_with
        if empty_response:
            return ChatResponse(content="", model="mock")
        prompt = messages[0].content
        # step 1 特征：含"从以下【小说大纲】中提取所有人物"
        if "提取所有人物" in prompt:
            return ChatResponse(content=extract_response, model="mock")
        # step 2：按姓名匹配
        for name, card in card_responses.items():
            if f"姓名：{name}" in prompt:
                return ChatResponse(content=card, model="mock")
        # fallback：返回第一个卡（避免 N 个 step 2 卡间顺序差异）
        first_card = next(iter(card_responses.values()))
        return ChatResponse(content=first_card, model="mock")

    m = AsyncMock()
    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    m.model = "mock-model"
    return m


# ===== _load_prompt =====


def test_load_prompt_extract_returns_str() -> None:
    p = _load_prompt("extract_characters")
    assert isinstance(p, str)
    assert "{outline}" in p


def test_load_prompt_generate_card_returns_str() -> None:
    p = _load_prompt("generate_card")
    assert isinstance(p, str)
    assert "{name}" in p
    assert "{role}" in p
    assert "{genre}" in p
    assert "{outline_context}" in p


def test_load_prompt_missing_section_raises() -> None:
    with pytest.raises(CharacterGenerationError):
        _load_prompt("nonexistent_section")


# ===== _normalize_role =====


def test_normalize_role_valid() -> None:
    for r in ("主角", "主角团", "反派", "正派", "队友", "其他"):
        assert _normalize_role(r) == r


def test_normalize_role_strip_whitespace() -> None:
    assert _normalize_role("  主角  ") == "主角"


def test_normalize_role_alias() -> None:
    assert _normalize_role("男主") == "主角"
    assert _normalize_role("女主") == "主角"
    assert _normalize_role("boss") == "反派"
    assert _normalize_role("盟友") == "正派"
    assert _normalize_role("伙伴") == "主角团"
    assert _normalize_role("npc") == "其他"


def test_normalize_role_invalid_fallback() -> None:
    assert _normalize_role("神秘角色") == "其他"
    assert _normalize_role("") == "其他"
    assert _normalize_role(None) == "其他"  # type: ignore[arg-type]


# ===== _trim_to_str =====


def test_trim_to_str_none() -> None:
    assert _trim_to_str(None) is None


def test_trim_to_str_str() -> None:
    assert _trim_to_str("hello") == "hello"
    assert _trim_to_str("  hello  ") == "hello"
    assert _trim_to_str("") is None
    assert _trim_to_str("   ") is None


def test_trim_to_str_non_str() -> None:
    assert _trim_to_str(42) == "42"
    assert _trim_to_str(1.5) == "1.5"
    assert _trim_to_str(True) == "True"


# ===== formatting 工具：extract_json_array / extract_yaml_block =====


def test_extract_json_array_simple() -> None:
    from src.core.llm.formatting import extract_json_array

    arr = extract_json_array('[{"name": "a"}, {"name": "b"}]')
    assert arr == [{"name": "a"}, {"name": "b"}]


def test_extract_json_array_with_think_block() -> None:
    from src.core.llm.formatting import extract_json_array

    text = '<think>\nthinking...\n</think>\n[{"x": 1}]'
    arr = extract_json_array(text)
    assert arr == [{"x": 1}]


def test_extract_json_array_invalid_raises() -> None:
    from src.core.llm.formatting import extract_json_array

    with pytest.raises(ValueError):
        extract_json_array("not a json array")


def test_extract_yaml_block_simple() -> None:
    from src.core.llm.formatting import extract_yaml_block

    text = "```yaml\nfoo: bar\nbaz: 42\n```"
    obj = extract_yaml_block(text)
    assert obj == {"foo": "bar", "baz": 42}


def test_extract_yaml_block_no_fence() -> None:
    from src.core.llm.formatting import extract_yaml_block

    text = "foo: bar\nbaz: 42"
    obj = extract_yaml_block(text)
    assert obj == {"foo": "bar", "baz": 42}


# ===== generate_from_outline：主路径 =====


@pytest.mark.asyncio
async def test_generate_from_outline_creates_characters(
    db_initialized: Path,
) -> None:
    from src.models.character import Character, CharacterVersion
    from src.models.novel import Novel

    # 先建一个 novel
    async with _session() as session:
        novel = Novel(name="凡人修仙传", genre="修仙", description="test")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    # 跑生成
    mock = _make_mock_llm()
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        result = await gen.generate_from_outline(
            novel_id=novel_id,
            outline={"outline_type": "complete", "volumes": []},
            genre="修仙",
        )

    # 校验返回
    assert result["novel_id"] == novel_id
    assert len(result["characters"]) == 3
    assert result["provider"] == "mock"
    assert result["model"] == "mock-model"
    names = {c.name for c in result["characters"]}
    assert names == {"韩立", "南宫婉", "墨大夫"}
    roles = {c.role for c in result["characters"]}
    assert roles == {"主角", "主角团", "反派"}

    # 校验入库 + 初始版本
    async with _session() as session:
        from sqlalchemy import select

        stmt = select(Character).where(Character.novel_id == novel_id)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 3
        for c in rows:
            assert c.current_version_id is not None
            vstmt = select(CharacterVersion).where(CharacterVersion.character_id == c.id)
            versions = (await session.execute(vstmt)).scalars().all()
            assert len(versions) == 1
            assert versions[0].change_reason == "initial"


@pytest.mark.asyncio
async def test_generate_from_outline_persists_growth_arc(db_initialized: Path) -> None:
    """成长弧线必须真的存进数据库（2026-10-25 巡检发现并修掉的真 bug）。

    以前 ``CharacterCreate`` schema 里**没有** ``growth_arc`` 字段 →
    Pydantic 默认 ``extra="ignore"`` → LLM 生成的成长弧线被**静默丢弃** →
    导出时"成长弧线"一栏永远是空的。
    """
    from sqlalchemy import select

    from src.models.character import Character
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="凡人修仙传", genre="修仙", description="test")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm()
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        await gen.generate_from_outline(
            novel_id=novel_id,
            outline={"outline_type": "complete", "volumes": []},
            genre="修仙",
        )

    async with _session() as session:
        stmt = select(Character).where(Character.novel_id == novel_id)
        rows = (await session.execute(stmt)).scalars().all()
        arcs = {c.name: c.growth_arc for c in rows}

    assert arcs["韩立"] == "从废材到飞升"
    assert arcs["南宫婉"] == "从宗派长老到双修伴侣"
    assert arcs["墨大夫"] == "被识破后败亡"


@pytest.mark.asyncio
async def test_generate_from_outline_novel_not_found(
    db_initialized: Path,
) -> None:
    mock = _make_mock_llm()
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(Exception) as exc_info:  # NovelNotFoundError
            await gen.generate_from_outline(
                novel_id=999999,  # 不存在
                outline={"volumes": []},
                genre="修仙",
            )
    # 应该是 NovelNotFoundError（或其父类 CharacterServiceError）
    assert isinstance(exc_info.value, NovelNotFoundError)


@pytest.mark.asyncio
async def test_generate_from_outline_outline_not_dict(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm()
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(CharacterGenerationError):
            await gen.generate_from_outline(
                novel_id=novel_id,
                outline="not a dict",  # type: ignore[arg-type]
                genre="x",
            )


@pytest.mark.asyncio
async def test_generate_from_outline_empty_extract(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm(extract_response="[]")
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        result = await gen.generate_from_outline(
            novel_id=novel_id,
            outline={"volumes": []},
            genre="x",
        )
    assert result["characters"] == []


@pytest.mark.asyncio
async def test_generate_from_outline_invalid_role_normalized(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    # LLM 返回非法 role
    extract = '[{"name": "路人甲", "role": "神秘角色"}]'
    mock = _make_mock_llm(
        extract_response=extract,
        card_responses={"路人甲": _CARD_HANLI},
    )
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        result = await gen.generate_from_outline(
            novel_id=novel_id, outline={"volumes": []}, genre="x"
        )
    assert len(result["characters"]) == 1
    assert result["characters"][0].role == "其他"  # 归到"其他"


@pytest.mark.asyncio
async def test_generate_from_outline_llm_error(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm(fail_with=RuntimeError("network down"))
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(CharacterGenerationError) as exc_info:
            await gen.generate_from_outline(novel_id=novel_id, outline={"volumes": []}, genre="x")
    assert "network down" in str(exc_info.value) or "RuntimeError" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_from_outline_empty_response(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm(empty_response=True)
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(CharacterGenerationError):
            await gen.generate_from_outline(novel_id=novel_id, outline={"volumes": []}, genre="x")


@pytest.mark.asyncio
async def test_generate_from_outline_invalid_json(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm(extract_response="不是合法 JSON 内容")
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(CharacterGenerationError):
            await gen.generate_from_outline(novel_id=novel_id, outline={"volumes": []}, genre="x")


@pytest.mark.asyncio
async def test_generate_from_outline_invalid_yaml(
    db_initialized: Path,
) -> None:
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    # step 1 合法，step 2 的卡返回非法 YAML
    mock = _make_mock_llm(
        extract_response='[{"name": "路人", "role": "其他"}]',
        card_responses={"路人": "this is : not : valid yaml: :::"},
    )
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        with pytest.raises(CharacterGenerationError):
            await gen.generate_from_outline(novel_id=novel_id, outline={"volumes": []}, genre="x")


@pytest.mark.asyncio
async def test_generate_from_outline_genre_default(
    db_initialized: Path,
) -> None:
    """不传 genre 时默认为 '通用'，不抛错。"""
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="x", genre="x", description="x")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    mock = _make_mock_llm(extract_response="[]")
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)
        # 不传 genre → 默认 "通用"
        result = await gen.generate_from_outline(novel_id=novel_id, outline={"volumes": []})
    assert result["characters"] == []


def test_no_loaded_prompt_at_import_time() -> None:
    """lru_cache 在 import 时不加载（懒加载）。"""
    import sys

    # 模块在 sys.modules 里
    assert "src.services.character_generator" in sys.modules
    # 不应自动加载 prompt 文件（无法直接断言；这里只保证模块导入不抛错）


# ===== 流式路径：并发入库（2026-10-24 回归）=====

_CARD_BY_NAME = {
    "韩立": _CARD_HANLI,
    "南宫婉": _CARD_NANGONG,
    "墨大夫": _CARD_MO,
}


class _StreamMockLLM:
    """支持 ``stream=True`` 的 mock LLM。

    ``barrier`` 用于让所有人物卡**在同一时刻**结束 LLM 阶段，
    从而确定性地触发并发入库的竞态（共用一个 AsyncSession）。
    """

    def __init__(self, barrier: asyncio.Barrier | None = None) -> None:
        self.barrier = barrier
        self.provider = "mock"
        self.model = "mock-model"

    async def chat(self, messages: list[ChatMessage], **kw: object) -> object:
        """返回 async generator（与 ``await llm.chat(..., stream=True)`` 匹配）。"""
        prompt = messages[0].content
        is_extract = "提取所有人物" in prompt
        if is_extract:
            payload = _EXTRACT_JSON
        else:
            payload = _CARD_HANLI
            for name, card in _CARD_BY_NAME.items():
                if f"姓名：{name}" in prompt:
                    payload = card
                    break

        async def _gen() -> object:
            yield payload
            # 只在**人物卡阶段**汇合；抽取阶段只有一个调用方，不能占 barrier 名额
            if self.barrier is not None and not is_extract:
                # 让所有卡在这里汇合 —— 之后同时进入入库阶段
                await self.barrier.wait()

        return _gen()


@pytest.mark.asyncio
async def test_stream_generate_saves_all_cards_when_generated_concurrently(
    db_initialized: Path,
) -> None:
    """回归：多张人物卡**并行**生成时，必须**全部**入库。

    2026-10-24 修的真实 bug：``stream_generate_from_outline`` 里每张卡的
    入库（``CharacterService.create`` → ``session.flush()/commit()``）也是并行的，
    而所有卡共用同一个 ``AsyncSession`` —— AsyncSession 不是并发安全的，
    同时 flush 会抛 ``InvalidRequestError: Session is already flushing``，
    结果是 4 张卡只存进去 1 张（用户看到的"已生成 4 个人物卡"其实是假的）。
    """
    from src.models.character import Character
    from src.models.novel import Novel

    async with _session() as session:
        novel = Novel(name="并发入库测试", genre="修仙", description="test")
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        novel_id = novel.id

    # 3 张卡在 LLM 阶段结束时汇合 → 同时进入入库阶段
    mock = _StreamMockLLM(barrier=asyncio.Barrier(3))

    events: list[dict] = []
    async with _session() as session:
        gen = CharacterGenerator(session, llm_client=mock)

        async def run() -> None:
            async for ev in gen.stream_generate_from_outline(
                novel_id=novel_id,
                outline={"outline_type": "complete", "volumes": []},
                genre="修仙",
            ):
                events.append(ev)

        await asyncio.wait_for(run(), timeout=15)

    # 三张卡都要入库
    async with _session() as session:
        from sqlalchemy import select

        stmt = select(Character).where(Character.novel_id == novel_id)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 3, f"只入库了 {len(rows)} 张卡（并发写 session 的竞态）"
        assert {r.name for r in rows} == {"韩立", "南宫婉", "墨大夫"}
        for r in rows:
            assert r.current_version_id is not None

    # done 事件的 saved_count 必须是**实际入库张数**，不能是"计划张数"
    done = [e for e in events if e.get("event") == "done"]
    assert len(done) == 1
    assert done[0]["saved_count"] == 3

    # 不能有失败事件
    assert [e for e in events if e.get("event") == "error"] == []
