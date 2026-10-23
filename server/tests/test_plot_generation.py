"""PlotService 单元测试（Phase 3.3 剧情生成）。

覆盖：
- generate() 单次返回 1 个版本
- generate() n=3 返回 3 个版本
- generate() 关键词为空 → PlotGenerationError
- generate() n_versions < 1 → PlotGenerationError
- generate() LLM 抛异常 → PlotGenerationError
- generate() LLM 返回空字符串 → PlotGenerationError
- _load_prompt 缓存命中
- _load_prompt 缺失文件 → PlotGenerationError
- clear_prompt_cache 工作
- stream_generate() 每个版本都完成 + 流正常结束（2026-10-23 回归）
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from loguru import logger

from src.core.llm.base import ChatMessage, ChatResponse
from src.services.inspiration_service import (
    PlotGenerationError,
    PlotService,
    _load_prompt,
)


@pytest.fixture
def mock_llm() -> AsyncMock:
    """返回固定响应内容的 mock LLM 客户端。"""

    async def fake_chat(messages: list[ChatMessage], **_kwargs: object) -> ChatResponse:
        # 让内容包含一些可识别的关键字，便于测试
        return ChatResponse(
            content="这是一段测试剧情。主角是 X，核心冲突是 Y，开场钩子是 Z。",
            model="mock-model",
        )

    m = AsyncMock()
    m.chat = AsyncMock(side_effect=fake_chat)
    m.provider = "mock"
    return m


@pytest.fixture(autouse=True)
def _clear_prompt_cache() -> None:
    """每个测试都 reload module + 清缓存，避免 conftest.temp_db 卸 src.* 后的污染。"""
    import importlib

    import src.services.inspiration_service as _svc

    importlib.reload(_svc)
    _svc.PlotService.clear_prompt_cache()
    # 让后续 from ... import 拿到的也是 reload 后的新引用
    globals()["PlotService"] = _svc.PlotService
    globals()["PlotGenerationError"] = _svc.PlotGenerationError
    globals()["_load_prompt"] = _svc._load_prompt
    yield
    _svc.PlotService.clear_prompt_cache()


# ===== generate() 基本流程 =====


@pytest.mark.asyncio
async def test_generate_one_version(mock_llm: AsyncMock) -> None:
    svc = PlotService(llm_client=mock_llm)
    results = await svc.generate("修仙", ["废柴", "逆袭"], n_versions=1)
    assert len(results) == 1
    assert "测试剧情" in results[0]
    # mock.chat 应被调 1 次
    assert mock_llm.chat.await_count == 1


@pytest.mark.asyncio
async def test_generate_three_versions(mock_llm: AsyncMock) -> None:
    svc = PlotService(llm_client=mock_llm)
    results = await svc.generate("都市", ["草根", "崛起"], n_versions=3)
    assert len(results) == 3
    # 串行调用 3 次
    assert mock_llm.chat.await_count == 3


@pytest.mark.asyncio
async def test_generate_passes_genre_and_keywords(mock_llm: AsyncMock) -> None:
    """验证 prompt 包含 genre 和 keywords（用 inspect.call_args 读）。"""
    svc = PlotService(llm_client=mock_llm)
    await svc.generate("悬疑", ["密室", "失忆"], n_versions=1)
    args, _kwargs = mock_llm.chat.call_args
    messages: list[ChatMessage] = args[0]
    assert len(messages) == 1
    assert "悬疑" in messages[0].content
    assert "密室" in messages[0].content
    assert "失忆" in messages[0].content


# ===== generate() 错误路径 =====


@pytest.mark.asyncio
async def test_generate_empty_keywords_raises(mock_llm: AsyncMock) -> None:
    svc = PlotService(llm_client=mock_llm)
    with pytest.raises(PlotGenerationError) as exc_info:
        await svc.generate("修仙", [], n_versions=1)
    assert "empty" in str(exc_info.value).lower() or "关键词" in str(exc_info.value)
    # LLM 不应被调用
    mock_llm.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_n_versions_zero_raises(mock_llm: AsyncMock) -> None:
    svc = PlotService(llm_client=mock_llm)
    with pytest.raises(PlotGenerationError):
        await svc.generate("修仙", ["x"], n_versions=0)


@pytest.mark.asyncio
async def test_generate_llm_exception_wrapped(mock_llm: AsyncMock) -> None:
    mock_llm.chat = AsyncMock(side_effect=RuntimeError("network error"))
    svc = PlotService(llm_client=mock_llm)
    with pytest.raises(PlotGenerationError) as exc_info:
        await svc.generate("修仙", ["x"], n_versions=1)
    assert "network error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_llm_empty_content_raises(mock_llm: AsyncMock) -> None:
    async def empty_chat(_messages: list[ChatMessage], **_kwargs: object) -> ChatResponse:
        return ChatResponse(content="   ")  # 全空白

    mock_llm.chat = AsyncMock(side_effect=empty_chat)
    svc = PlotService(llm_client=mock_llm)
    with pytest.raises(PlotGenerationError):
        await svc.generate("修仙", ["x"], n_versions=1)


# ===== prompt loader =====


def test_load_prompt_returns_str() -> None:
    prompt = _load_prompt("plot_generation")
    assert isinstance(prompt, str)
    assert "{genre}" in prompt
    assert "{keywords}" in prompt


def test_load_prompt_missing_file_raises(tmp_path: Path) -> None:
    """prompt 文件缺失 → PlotGenerationError。

    用 importlib.reload 确保 module 引用最新（conftest.temp_db 会卸 src.*）
    """
    import importlib

    import src.services.inspiration_service as _svc

    importlib.reload(_svc)
    _svc._PROMPTS_DIR = tmp_path  # type: ignore[attr-defined]
    _svc._load_prompt.cache_clear()  # type: ignore[attr-defined]
    try:
        with pytest.raises(_svc.PlotGenerationError):
            _svc._load_prompt("nonexistent")
    finally:
        _svc._load_prompt.cache_clear()  # type: ignore[attr-defined]


def test_load_prompt_cache_works() -> None:
    """二次加载走 lru_cache（不计文件 IO）。"""
    p1 = _load_prompt("plot_generation")
    p2 = _load_prompt("plot_generation")
    assert p1 is p2  # 同一对象（lru_cache）


def test_clear_prompt_cache_works() -> None:
    _load_prompt("plot_generation")
    PlotService.clear_prompt_cache()
    # cache 已清；再加载仍能成功
    p = _load_prompt("plot_generation")
    assert isinstance(p, str)


# ===== 边界：n_versions 默认值 =====


@pytest.mark.asyncio
async def test_generate_default_n_versions(mock_llm: AsyncMock) -> None:
    """不传 n_versions → 用默认 3。"""
    svc = PlotService(llm_client=mock_llm)
    results = await svc.generate("言情", ["替嫁", "契约"])
    assert len(results) == 3
    assert mock_llm.chat.await_count == 3


# ===== 端到端：prompt 模板格式化 =====


@pytest.mark.asyncio
async def test_generate_uses_real_prompt_template(mock_llm: AsyncMock, tmp_path: Path) -> None:
    """prompt 模板被真实加载并 format 进去（不靠硬编码）。"""
    # 临时替换 prompt 文件，确保 format 后的字符串里 genre/keywords 都替换
    custom = tmp_path / "plot_generation.yaml"
    custom.write_text(
        yaml.safe_dump(
            {"version": 1, "prompt": "题材={genre} 词={keywords}"},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    import importlib

    import src.services.inspiration_service as _svc

    importlib.reload(_svc)
    _svc._PROMPTS_DIR = tmp_path  # type: ignore[attr-defined]
    _svc._load_prompt.cache_clear()  # type: ignore[attr-defined]
    try:
        svc = _svc.PlotService(llm_client=mock_llm)
        await svc.generate("都市", ["草根"], n_versions=1)
        args, _ = mock_llm.chat.call_args
        assert args[0][0].content == "题材=都市 词=草根"
    finally:
        _svc._load_prompt.cache_clear()  # type: ignore[attr-defined]


# ===== _strip_thinking =====


def test_strip_thinking_removes_block() -> None:
    from src.services.inspiration_service import _strip_thinking

    raw = "<think>The user wants X. Let me think.\n思路\n</think>\n\n这是最终剧情。主角是 X。"
    out = _strip_thinking(raw)
    assert "<think>" not in out
    assert "思路" not in out
    assert "最终剧情" in out


def test_strip_thinking_passthrough_when_no_block() -> None:
    from src.services.inspiration_service import _strip_thinking

    raw = "直接是正文，没有 think 块。"
    assert _strip_thinking(raw) == raw


def test_strip_thinking_handles_multiple_blocks() -> None:
    from src.services.inspiration_service import _strip_thinking

    raw = "<think>第一段</think>正文<think>第二段</think>尾巴"
    out = _strip_thinking(raw)
    assert "第一段" not in out
    assert "第二段" not in out
    assert "正文" in out
    assert "尾巴" in out


@pytest.mark.asyncio
async def test_generate_strips_thinking_from_output(mock_llm: AsyncMock) -> None:
    """回归：minimax 推理模型会输出 <think> 块，service 必须剥掉。"""
    import importlib

    import src.services.inspiration_service as _svc

    importlib.reload(_svc)

    async def thinking_chat(_messages: list[ChatMessage], **_kwargs: object) -> ChatResponse:
        return ChatResponse(
            content="<think>让我想想。\n\n需要三要素。</think>\n\n这是干净的剧情正文。",
        )

    mock_llm.chat = AsyncMock(side_effect=thinking_chat)
    svc = _svc.PlotService(llm_client=mock_llm)
    results = await svc.generate("修仙", ["飞升"], n_versions=1)
    assert len(results) == 1
    assert "<think>" not in results[0]
    assert "干净的剧情正文" in results[0]


@pytest.mark.asyncio
async def test_generate_raises_if_only_thinking(mock_llm: AsyncMock) -> None:
    """剥掉 thinking 后如果全空（模型只输出思考）→ PlotGenerationError。"""
    import importlib

    import src.services.inspiration_service as _svc

    importlib.reload(_svc)

    async def only_thinking(_messages: list[ChatMessage], **_kwargs: object) -> ChatResponse:
        return ChatResponse(content="<think>全程在思考，没写正文。</think>")

    mock_llm.chat = AsyncMock(side_effect=only_thinking)
    svc = _svc.PlotService(llm_client=mock_llm)
    with pytest.raises(_svc.PlotGenerationError) as exc_info:
        await svc.generate("修仙", ["x"], n_versions=1)
    assert "empty" in str(exc_info.value).lower()


# ===== 流式生成（2026-10-23 回归）=====


class _StreamMockLLM:
    """支持 ``chat(..., stream=True)`` 的 mock 客户端。"""

    provider = "mock"
    model = "mock-model"

    def __init__(self, chunks: list[str] | None = None) -> None:
        self._chunks = chunks or ["主角", "历经", "苦难"]
        self.chat_calls = 0

    async def chat(self, messages: list[ChatMessage], **kwargs: object):
        self.chat_calls += 1
        if kwargs.get("stream"):
            chunks = self._chunks

            async def gen():
                for c in chunks:
                    await asyncio.sleep(0)
                    yield c

            return gen()
        return ChatResponse(content="".join(self._chunks), model="mock-model")


@pytest.mark.asyncio
async def test_stream_generate_delivers_all_versions_and_terminates() -> None:
    """回归：3 个版本必须**全部**完成，流必须**正常结束**。

    2026-10-23 修的真实 bug：``version_runner(i + 1)`` 配 ``queues[idx]``，
    1 起的下标去取 0 起的列表 → 最后一个版本 IndexError。
    异常发生在 try 之外 → 那个 runner 直接死掉、**结束哨兵永远不 put** →
    主协程一直等 → 流式端点永久挂死（客户端看着像"卡住了"）。

    这里的 ``wait_for`` 是保险：旧代码会在这里超时失败，而不是卡住整个测试。
    """
    llm = _StreamMockLLM()
    svc = PlotService(llm_client=llm)
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("修仙", ["逆袭"], n_versions=3):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)

    done = [e for e in events if e["event"] == "version_done"]
    assert len(done) == 3
    assert {e["index"] for e in done} == {1, 2, 3}
    # 每个版本都该有 delta
    assert len([e for e in events if e["event"] == "delta"]) == 9
    # 整流以 done 收尾
    assert events[-1]["event"] == "done"
    # 3 个版本 = 3 次 LLM 调用
    assert llm.chat_calls == 3


@pytest.mark.asyncio
async def test_stream_generate_single_version_terminates() -> None:
    """n_versions=1 同样要正常结束（旧代码这里就越界了）。"""
    llm = _StreamMockLLM()
    svc = PlotService(llm_client=llm)
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("都市", ["草根"], n_versions=1):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)
    assert len([e for e in events if e["event"] == "version_done"]) == 1
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_stream_generate_reports_llm_error_and_terminates() -> None:
    """LLM 报错时也要吐 error 事件并正常结束（不能挂死）。"""

    class _BoomLLM(_StreamMockLLM):
        async def chat(self, messages: list[ChatMessage], **kwargs: object):
            self.chat_calls += 1
            raise RuntimeError("upstream exploded")

    llm = _BoomLLM()
    svc = PlotService(llm_client=llm)
    events: list[dict] = []

    async def run() -> None:
        async for ev in svc.stream_generate("修仙", ["x"], n_versions=2):
            events.append(ev)

    await asyncio.wait_for(run(), timeout=10)
    assert len([e for e in events if e["event"] == "error"]) == 2
    assert events[-1]["event"] == "done"


# 静默 logger 警告（如果有）
logger.disable("src.services.inspiration_service")
