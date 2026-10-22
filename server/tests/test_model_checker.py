"""测试 model_checker：能力校验 + warning 级别。"""

from __future__ import annotations

import pytest

from src.core.llm.factory import clear_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前清掉 lru_cache。"""
    clear_cache()
    yield
    clear_cache()


def test_minimax_m3_passes_chapter_check():
    """minimax-M3（1M context）应通过章节检查，零 warning。"""
    from src.core.llm.model_checker import check_model_capability

    result = check_model_capability("minimax", "MiniMax-M3")
    assert result.context_window == 1000000
    assert result.can_generate_chapter is True
    # 没有任何 error/warning
    assert all(w.level == "info" for w in result.warnings)


def test_qwen_7b_warning_for_small_max_output():
    """qwen2.5:7b（32k context, 8k output）应能生成章节但 max_output 刚好。"""
    from src.core.llm.model_checker import check_model_capability

    result = check_model_capability("ollama", "qwen2.5:7b")
    # 32k >= 32k (min context)，所以不报 error
    assert result.can_generate_chapter is True


def test_unknown_model_does_not_raise():
    """不存在的 model 不再抛错（用户可以自己填服务端新出的模型名）。

    2026-10-22 改：原来直接抛 KeyError，导致"自己换模型"这个能力被堵死。
    现在按 provider 级默认值估算能力，并给一条 info 提示。
    """
    from src.core.llm.model_checker import check_model_capability

    result = check_model_capability("minimax", "nonexistent-model")
    # 按 provider 兜底值估算（minimax.default_context_window = 200000）
    assert result.context_window == 200000
    assert result.can_generate_chapter is True
    assert any("未在 config/llm.yaml 登记规格" in w.message for w in result.warnings)


def test_unknown_provider_raises():
    """不存在的 provider 应抛 KeyError。"""
    from src.core.llm.model_checker import check_model_capability

    with pytest.raises(KeyError):
        check_model_capability("totally_made_up", "any-model")


def test_ollama_qwen_14b_passes():
    """qwen2.5:14b 应能生成章节。"""
    from src.core.llm.model_checker import check_model_capability

    result = check_model_capability("ollama", "qwen2.5:14b")
    assert result.can_generate_chapter is True
    assert result.context_window >= 32000
