"""思考内容净身单元测试（2026-10-29 新增）。

背景：用户实测生成剧情时，剧情卡片里直接流出模型的**英文规划文字**
（"viation. Opening hook. Need count 200-40"）。用户要求
「纯中文思考输出，不要含有代码以及英文」。

覆盖：
- ``sanitize_thinking``：英文/代码被删、中文保留、纯英文被清空
- ``thinking_event``：dirty 标记 + max_chars 截断
"""

from __future__ import annotations

from src.core.llm.thinking import THINKING_PLACEHOLDER, sanitize_thinking, thinking_event

# ===== sanitize_thinking =====


def test_pure_chinese_is_kept_verbatim() -> None:
    assert sanitize_thinking("好的，先构思冲突。") == "好的，先构思冲突。"


def test_english_words_are_removed() -> None:
    """英文单词被删，剩下的中文保留（不能整段丢 —— 否则界面像卡死）。"""
    out = sanitize_thinking("现在构思 Opening hook 部分")
    assert "Opening" not in out
    assert "hook" not in out
    assert "现在构思" in out
    assert "部分" in out


def test_pure_english_is_cleared() -> None:
    """整段都是英文 → 清空（前端会用占位符顶上）。"""
    assert sanitize_thinking("Need count 200-40") == ""
    assert sanitize_thinking("viation. Opening hook.") == ""


def test_code_markers_are_removed() -> None:
    """代码痕迹（花括号、等号、代码块）被删。"""
    out = sanitize_thinking("调用 `self.foo()` 处理数据")
    assert "self" not in out
    assert "foo" not in out
    assert "调用" in out
    assert "处理数据" in out


def test_json_blob_is_cleared() -> None:
    assert sanitize_thinking('{"chapters": [{"title": "A"}]}') == ""


def test_digits_alone_are_cleared() -> None:
    """只剩数字（没汉字）→ 没有展示价值 → 清空。"""
    assert sanitize_thinking("200-400") == ""


def test_full_width_letters_are_removed() -> None:
    """全角字母也是英文，同样要删。"""
    out = sanitize_thinking("这里有ＡＢＣ三个字母")
    assert "Ａ" not in out
    assert "Ｂ" not in out
    assert "这里有" in out


def test_chinese_punctuation_is_kept() -> None:
    out = sanitize_thinking("他说：「别动。」")
    assert "「" in out
    assert "」" in out
    assert "。" in out


def test_empty_input_returns_empty() -> None:
    assert sanitize_thinking("") == ""
    assert sanitize_thinking("   ") == ""


# ===== thinking_event =====


def test_thinking_event_marks_dirty_and_cleans() -> None:
    event = thinking_event("Opening hook 现在构思")
    assert event["event"] == "thinking"
    assert "Opening" not in event["text"]
    assert event.get("dirty") is True


def test_thinking_event_clean_has_no_dirty_flag() -> None:
    event = thinking_event("先想清楚主线")
    assert event["text"] == "先想清楚主线"
    assert "dirty" not in event


def test_thinking_event_truncates_to_max_chars() -> None:
    event = thinking_event("一二三四五六七八九十", max_chars=4)
    assert event["text"] == "一二三四"
    assert len(event["text"]) == 4


def test_thinking_event_keeps_extra_fields() -> None:
    event = thinking_event("构思中", index=2, phase="card")
    assert event["index"] == 2
    assert event["phase"] == "card"


def test_placeholder_is_pure_chinese() -> None:
    """占位符本身不能夹带英文/代码。"""
    assert sanitize_thinking(THINKING_PLACEHOLDER) == THINKING_PLACEHOLDER
    assert not any(c.isascii() and c.isalpha() for c in THINKING_PLACEHOLDER)
