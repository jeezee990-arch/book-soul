"""``ThinkSplitter`` 的单元测试（2026-10-24 新增）。

为什么需要这个类
----------------
推理模型（minimax / 部分 mimo）会先吐一整段 ``<think>...</think>``
再开始吐正文。以前各 service 都用 ``if "<think>" in delta: continue`` 直接丢掉 ——
思考可能持续好几秒，这段时间前端一个字都收不到，用户看到的就是"卡住不动"。

``ThinkSplitter`` 把流式输出拆成「正文」和「思考」两路，
让思考内容能作为独立的 ``thinking`` 事件转发给前端。
"""

from __future__ import annotations

from src.core.llm.streaming import KIND_TEXT, KIND_THINK, ThinkSplitter


def test_plain_text_passes_through() -> None:
    """没有 think 标记时，原样透出。"""
    s = ThinkSplitter()
    assert s.feed("普通正文") == [(KIND_TEXT, "普通正文")]
    assert s.in_think is False


def test_think_block_is_split_out() -> None:
    """``<think>...</think>`` 整块被拆成 think，正文部分仍是 text。"""
    s = ThinkSplitter()
    assert s.feed("<think>思考中</think>正文") == [
        (KIND_THINK, "思考中"),
        (KIND_TEXT, "正文"),
    ]
    assert s.in_think is False


def test_think_block_split_across_chunks() -> None:
    """think 块被拆到多个 chunk 里也能正确还原。

    这是最常见的实际情况 —— chunk 边界跟 ``<think>`` 标签没有任何关系。
    """
    s = ThinkSplitter()
    assert s.feed("<think>我") == [(KIND_THINK, "我")]
    assert s.in_think is True
    assert s.feed("在想") == [(KIND_THINK, "在想")]
    assert s.feed("</think>") == []
    assert s.in_think is False
    assert s.feed("正文") == [(KIND_TEXT, "正文")]


def test_text_before_think_is_kept() -> None:
    """``<think>`` 之前的正文不能被一起当成思考内容丢掉。"""
    s = ThinkSplitter()
    assert s.feed("前面正文<think>思考</think>后面正文") == [
        (KIND_TEXT, "前面正文"),
        (KIND_THINK, "思考"),
        (KIND_TEXT, "后面正文"),
    ]


def test_same_chunk_has_both_open_and_close() -> None:
    """一个 chunk 里同时有 ``<think>`` 和 ``</think>`` → 思考内容不能混进正文。

    旧写法 ``if "<think>" in delta and "</think>" not in delta: continue``
    在这种情况下会把**整个 chunk**（含思考内容）当正文吐出去。
    """
    s = ThinkSplitter()
    parts = s.feed("<think>中间思考</think>真实正文")
    assert parts == [
        (KIND_THINK, "中间思考"),
        (KIND_TEXT, "真实正文"),
    ]
    assert "思考" not in "".join(t for k, t in parts if k == KIND_TEXT)


def test_empty_and_whitespace_only_chunks_are_dropped() -> None:
    """空片段不产出（避免前端收到空 delta 触发无谓渲染）。"""
    s = ThinkSplitter()
    assert s.feed("") == []
    assert s.feed("<think></think>") == []


def test_unterminated_think_block_keeps_state() -> None:
    """流在 think 块中间断掉时，状态保持（后续 feed 仍按 think 处理）。"""
    s = ThinkSplitter()
    s.feed("<think>还没说完")
    assert s.in_think is True
    assert s.feed("还在想") == [(KIND_THINK, "还在想")]
    assert s.in_think is True
