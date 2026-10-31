"""正文排版归一化测试（2026-10-30）。

覆盖用户实测反馈的三类问题：
- 正文多出空余字符（汉字间空格）
- 没有分段分行（模型不输出段落）
- 字数虚高（把换行/空格算进字数）
"""

from __future__ import annotations

from src.core.prose_format import (
    ProseFormatter,
    count_prose_words,
    normalize_whitespace,
    split_paragraphs,
)


def _run(chunks: list[str]) -> str:
    """把增量喂进格式化器，返回完整输出。"""
    fmt = ProseFormatter()
    out = "".join(fmt.feed(c) for c in chunks)
    out += fmt.finish()
    return out


class TestCountProseWords:
    """字数口径 = 非空白字符数（含中文标点，与 Word 一致）。"""

    def test_counts_hanzi_and_punctuation(self) -> None:
        assert count_prose_words("你好世界") == 4
        assert count_prose_words("你好，世界！") == 6

    def test_ignores_whitespace_and_newlines(self) -> None:
        assert count_prose_words("你 好\n\n世界") == 4
        assert count_prose_words("甲。\n\n乙。") == 4

    def test_english_word_counts_per_character(self) -> None:
        # 非空白字符数口径：英文按字符算
        assert count_prose_words("hello world") == 10

    def test_empty(self) -> None:
        assert count_prose_words("") == 0

    def test_matches_word_like_count_on_real_broken_data(self) -> None:
        """用户实测：坏数据 5338 字符里含 2024 个换行 → 真实 3314。"""
        broken = "山\n\n门前的\n\n铜\n\n钟连\n\n响三\n\n声"
        assert len(broken) == 20  # 10 个正文字 + 5 组 \n\n
        assert count_prose_words(broken) == 10


class TestNormalizeWhitespace:
    def test_removes_space_between_hanzi(self) -> None:
        assert normalize_whitespace("山 门 前 的") == "山门前的"

    def test_keeps_space_between_english_words(self) -> None:
        assert normalize_whitespace("hello world") == "hello world"

    def test_keeps_space_between_hanzi_and_english(self) -> None:
        assert normalize_whitespace("他说 hi 走了") == "他说 hi 走了"


class TestSplitParagraphs:
    def test_splits_on_blank_line(self) -> None:
        assert split_paragraphs("第一段\n\n第二段") == ["第一段", "第二段"]

    def test_splits_on_single_newline(self) -> None:
        assert split_paragraphs("第一段\n第二段") == ["第一段", "第二段"]

    def test_drops_empty_segments(self) -> None:
        assert split_paragraphs("\n\n甲\n\n\n\n乙\n\n") == ["甲", "乙"]

    def test_empty(self) -> None:
        assert split_paragraphs("") == []


class TestProseFormatter:
    def test_model_paragraph_breaks_are_preserved(self) -> None:
        raw = "第一段内容。\n\n第二段内容。"
        out = _run([raw])
        assert out.count("\n\n") == 1
        assert "第一段内容。" in out
        assert "第二段内容。" in out

    def test_multiple_blank_lines_collapse_to_one_break(self) -> None:
        out = _run(["甲。\n\n\n\n乙。"])
        assert out.count("\n\n") == 1

    def test_removes_spaces_between_hanzi(self) -> None:
        out = _run(["山 门 前 的 铜 钟"])
        assert " " not in out
        assert "山门前的铜钟" in out

    def test_keeps_space_between_english_words(self) -> None:
        out = _run(["he said hello world"])
        assert "hello world" in out

    def test_fallback_breaks_long_paragraph(self) -> None:
        """模型完全不给段落时，也要靠句末标点兜底断段。"""
        sentences = "".join(f"这是第{i}句话内容足够长可以触发断段规则。" for i in range(6))
        out = _run([sentences])
        assert out.count("\n\n") >= 1, "长段落必须被兜底断段"

    def test_short_text_stays_one_paragraph(self) -> None:
        out = _run(["很短。"])
        assert "\n\n" not in out

    def test_dialogue_ends_paragraph(self) -> None:
        """对白收尾后另起一段，多人对话才能区分。"""
        text = (
            "沈砚抬起头看着面前的执事那人开口问了一句很长的关于测灵石的问题"
            "「这是什么意思」执事没有回答"
        )
        out = _run([text])
        assert "\n\n" in out, "对白结束后应另起一段"

    def test_output_is_stable_across_chunk_boundaries(self) -> None:
        """同一个文本按不同切分喂入，结果应一致（增量处理不能依赖批次）。"""
        text = "沈砚走到测灵石前站定。执事翻开名册开始点名。「沈砚」他应了一声。"
        whole = _run([text])
        chunked = _run(list(text))
        assert whole == chunked

    def test_no_paragraph_mark_at_stream_start(self) -> None:
        out = _run(["开头。"])
        assert not out.startswith("\n\n")

    def test_no_trailing_paragraph_mark(self) -> None:
        out = _run(["结尾。"])
        assert not out.endswith("\n\n")


class TestConsecutiveDialogue:
    """连续对白（换人说话）必须各自成段 —— 用户实测的三大痛点之一。

    旧规则要求「整段满 30 字」才在对白后断段，于是
    ``“沈砚？”“沈家村，沈砚。”“供药旧户？”“是。”``
    这种短促的连续对白全挤在一段里，读者分不清谁在说话。
    """

    def test_curl_quotes_split_consecutive_dialogue(self) -> None:
        out = _run(["“沈砚？”“沈家村，沈砚。”“供药旧户？”“是。”"])
        assert out.count("\n\n") == 3, f"四句对白应断成四段，实际: {out!r}"

    def test_corner_quote_dialogue_split(self) -> None:
        out = _run(["「甲？」「乙。」「丙？」"])
        assert out.count("\n\n") == 2, f"三句对白应断成三段，实际: {out!r}"

    def test_dialogue_followed_by_narration_is_not_split(self) -> None:
        """对白后直接接叙述句 → 不该断（叙述和引号之间有别的字）。"""
        out = _run(["“沈砚。”执事翻开名册开始点名登记。"])
        assert "\n\n" not in out, f"对白后接叙述不该断段，实际: {out!r}"

    def test_two_dialogues_are_split(self) -> None:
        """两句对白挨在一起 → 算换人说话 → 断。"""
        out = _run(["“沈砚？”“执事翻开名册。”"])
        assert out.count("\n\n") == 1, f"两句对白应断成两段，实际: {out!r}"

    def test_single_dialogue_not_split(self) -> None:
        out = _run(["“沈砚。”"])
        assert "\n\n" not in out

    def test_stable_across_chunk_boundaries(self) -> None:
        text = "“沈砚？”“沈家村，沈砚。”“供药旧户？”“是。”"
        assert _run([text]) == _run(list(text))

    def test_real_user_data_shape(self) -> None:
        """用户库里真实出现的形态（修复后仍应再拆开对白）。"""
        out = _run(["“沈砚？”“沈家村，沈砚。”“供药旧户？”“是。”执事接过他腰间的药引。"])
        paras = [p for p in out.split("\n\n") if p]
        assert paras[0] == "“沈砚？”"
        assert paras[1] == "“沈家村，沈砚。”"
        assert paras[2] == "“供药旧户？”"
        assert paras[3] == "“是。”执事接过他腰间的药引。"

    def test_quoted_words_are_not_split(self) -> None:
        """引用词语（``“沈”“砚”``）不是换人说话 → 不能拆。

        判据：引号**内部**没有句末标点 → 只是引用，不是说完了一句话。
        """
        text = "三字。笔锋随即横过沈砚的名字，自左至右，将“沈”“砚”二字一齐划去。"
        out = _run([text])
        assert "\n\n" not in out, f"引用词语不该被拆段，实际: {out!r}"
