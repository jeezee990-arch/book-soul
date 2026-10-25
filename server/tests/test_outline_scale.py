"""大纲规模参数化单元测试（2026-10-25 新增）。

覆盖：
- ``OutlineScale`` 的分卷计算（均分 + 前几卷多 1 章，总和严格等于总章数）
- ``normalize_scale`` 的缺省与越界裁剪
- ``parse_scale_from_text`` 的各种自然语言写法
"""

from __future__ import annotations

import pytest

from src.core.outline_scale import (
    DEFAULT_CHAPTERS_PER_VOLUME,
    DEFAULT_TOTAL_CHAPTERS,
    DEFAULT_WORDS_PER_CHAPTER,
    MAX_TOTAL_CHAPTERS,
    OutlineScale,
    normalize_scale,
    parse_scale_from_text,
)

# ===== 分卷计算 =====


def test_volume_count_is_ceil() -> None:
    scale = OutlineScale(total_chapters=100, chapters_per_volume=10, words_per_chapter=3000)
    assert scale.volume_count == 10
    assert scale.volume_chapter_counts == [10] * 10


def test_volume_chapter_counts_sum_equals_total() -> None:
    """总章数不能整除时，各卷章数之和仍要严格等于总章数（硬指标）。"""
    scale = OutlineScale(total_chapters=25, chapters_per_volume=10, words_per_chapter=3000)
    counts = scale.volume_chapter_counts
    assert sum(counts) == 25
    assert scale.volume_count == 3
    assert counts == [9, 8, 8]


def test_total_words() -> None:
    scale = OutlineScale(total_chapters=100, chapters_per_volume=10, words_per_chapter=3000)
    assert scale.total_words == 300000


def test_volume_plan_text() -> None:
    scale = OutlineScale(total_chapters=20, chapters_per_volume=10, words_per_chapter=3000)
    assert scale.volume_plan == "第1卷 10 章；第2卷 10 章"


# ===== normalize =====


def test_normalize_uses_defaults_when_none() -> None:
    scale = normalize_scale()
    assert scale.total_chapters == DEFAULT_TOTAL_CHAPTERS
    assert scale.chapters_per_volume == DEFAULT_CHAPTERS_PER_VOLUME
    assert scale.words_per_chapter == DEFAULT_WORDS_PER_CHAPTER


def test_normalize_clamps_out_of_range() -> None:
    scale = normalize_scale(
        total_chapters=99999,
        chapters_per_volume=-5,
        words_per_chapter=1,
    )
    assert scale.total_chapters == MAX_TOTAL_CHAPTERS
    assert scale.chapters_per_volume >= 1
    assert scale.words_per_chapter >= 500


def test_normalize_caps_chapters_per_volume_by_total() -> None:
    """每卷章数不能超过总章数（否则会算出 0 章的卷）。"""
    scale = normalize_scale(total_chapters=5, chapters_per_volume=20)
    assert scale.chapters_per_volume == 5
    assert scale.volume_count == 1
    assert scale.volume_chapter_counts == [5]


# ===== 自然语言解析 =====


@pytest.mark.parametrize(
    ("text", "expected_total"),
    [
        ("共100章", 100),
        ("全书 100 章", 100),
        ("总章数 100 章", 100),
        ("计划写30章", 30),
        ("30章左右", 30),
    ],
)
def test_parse_total_chapters(text: str, expected_total: int) -> None:
    scale = parse_scale_from_text(text)
    assert scale is not None
    assert scale.total_chapters == expected_total


def test_parse_ignores_per_volume_chapter_count_as_total() -> None:
    """「每卷10章」里的 10 **不能**被当成总章数。"""
    scale = parse_scale_from_text("每卷10章")
    assert scale is not None
    assert scale.chapters_per_volume == 10
    assert scale.total_chapters == DEFAULT_TOTAL_CHAPTERS


def test_parse_ignores_chapter_number_as_total() -> None:
    """「第10章」里的 10 不能被当成总章数。"""
    scale = parse_scale_from_text("第10章开始")
    assert scale is None or scale.total_chapters == DEFAULT_TOTAL_CHAPTERS


def test_parse_per_chapter_words() -> None:
    scale = parse_scale_from_text("每章3000字")
    assert scale is not None
    assert scale.words_per_chapter == 3000


def test_parse_per_chapter_words_with_k_suffix() -> None:
    scale = parse_scale_from_text("每章 3k 字")
    assert scale is not None
    assert scale.words_per_chapter == 3000


def test_parse_total_words_wan() -> None:
    """30 万字 ÷ 3000 字/章 = 100 章。"""
    scale = parse_scale_from_text("完本30万字")
    assert scale is not None
    assert scale.total_chapters == 100


def test_parse_total_words_w_letter() -> None:
    scale = parse_scale_from_text("全书30w字")
    assert scale is not None
    assert scale.total_chapters == 100


def test_parse_combined_chapters_and_words() -> None:
    """用户真实场景：「总章数100章」「每章3000字」「完本30万字」。"""
    scale = parse_scale_from_text("总章数100章\n每章3000字\n完本30万字")
    assert scale is not None
    assert scale.total_chapters == 100
    assert scale.words_per_chapter == 3000
    assert scale.chapters_per_volume == DEFAULT_CHAPTERS_PER_VOLUME


def test_parse_words_only_derives_chapters() -> None:
    """只给总字数 + 每章字数 → 折算出章数。"""
    scale = parse_scale_from_text("每章3000字，完本30万字")
    assert scale is not None
    assert scale.total_chapters == 100


def test_parse_chinese_numerals() -> None:
    scale = parse_scale_from_text("共一百二十章")
    assert scale is not None
    assert scale.total_chapters == 120


def test_parse_returns_none_when_nothing_found() -> None:
    assert parse_scale_from_text("主角是废柴，偶然获得传承") is None
    assert parse_scale_from_text("") is None
    assert parse_scale_from_text("   ") is None


def test_parse_multi_line_ideas() -> None:
    """多个想法拼成的多行文本也要能解析。"""
    scale = parse_scale_from_text("不要系统流\n主角是废柴\n共100章\n每卷10章\n每章3000字")
    assert scale is not None
    assert scale.total_chapters == 100
    assert scale.chapters_per_volume == 10
    assert scale.words_per_chapter == 3000
