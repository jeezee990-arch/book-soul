"""种子词导入文本解析测试（纯逻辑）。

覆盖 ``services/wordbank_importer.py``：
- 换行 / 逗号 / 顿号 / 分号 / 竖线 分隔
- ``分类:词条`` 前缀（行首 + 词条级；英文 key 与中文别名）
- 未知分类 → 逐行报错
- 注释行、空行
- 词条过长
- 批次内去重
"""

from __future__ import annotations

from src.services.wordbank_importer import (
    CATEGORY_ALIASES,
    ParseResult,
    parse_import_text,
    resolve_category,
)

CATEGORIES = ["themes", "characters", "plots", "scenes", "items"]


def _words(result: ParseResult) -> list[tuple[str, str]]:
    """把解析结果压成 (分类, 词) 列表，方便断言。"""
    return [(w.category, w.word) for w in result.words]


def test_parse_empty_text() -> None:
    result = parse_import_text("")
    assert result.words == []
    assert result.issues == []


def test_parse_newline_separated() -> None:
    result = parse_import_text("逆袭\n草根", valid_categories=CATEGORIES)
    assert _words(result) == [("themes", "逆袭"), ("themes", "草根")]


def test_parse_all_delimiters() -> None:
    """逗号 / 中文逗号 / 顿号 / 分号 / 中文分号 / 竖线 / 制表符。"""
    result = parse_import_text("a,b，c、d;e；f|g\th", valid_categories=CATEGORIES)
    assert [w.word for w in result.words] == ["a", "b", "c", "d", "e", "f", "g", "h"]


def test_parse_space_is_not_a_delimiter() -> None:
    """空格不当分隔符（英文词可能带空格）。"""
    result = parse_import_text("dark lord", valid_categories=CATEGORIES)
    assert [w.word for w in result.words] == ["dark lord"]


def test_parse_comment_lines_skipped() -> None:
    result = parse_import_text("# 注释\n// 注释\n逆袭", valid_categories=CATEGORIES)
    assert [w.word for w in result.words] == ["逆袭"]
    assert result.issues == []


def test_parse_line_prefix_applies_to_whole_line() -> None:
    result = parse_import_text("themes:逆袭,草根", valid_categories=CATEGORIES)
    assert _words(result) == [("themes", "逆袭"), ("themes", "草根")]


def test_parse_line_prefix_chinese_alias() -> None:
    result = parse_import_text("人物：师姐", valid_categories=CATEGORIES)
    assert _words(result) == [("characters", "师姐")]


def test_parse_token_prefix_overrides_line_prefix() -> None:
    """词条自带前缀时，只有那个词换分类。"""
    result = parse_import_text("themes:逆袭,characters:师姐", valid_categories=CATEGORIES)
    assert _words(result) == [("themes", "逆袭"), ("characters", "师姐")]


def test_parse_unknown_prefix_reports_issue() -> None:
    result = parse_import_text("未知分类:词条", valid_categories=CATEGORIES)
    assert result.words == []
    assert len(result.issues) == 1
    assert "第 1 行" in result.issues[0].describe()
    assert "未知分类" in result.issues[0].describe()


def test_parse_unknown_prefix_in_token_reports_issue() -> None:
    result = parse_import_text("逆袭,瞎写:词", valid_categories=CATEGORIES)
    assert _words(result) == [("themes", "逆袭")]
    assert len(result.issues) == 1


def test_parse_prefix_not_in_valid_categories_reports_issue() -> None:
    """前缀是合法别名，但当前板块没这个分类 → 同样报错。"""
    result = parse_import_text("items:飞剑", valid_categories=["themes", "characters"])
    assert result.words == []
    assert len(result.issues) == 1


def test_parse_too_long_word_reports_issue() -> None:
    result = parse_import_text("词" * 100, valid_categories=CATEGORIES)
    assert result.words == []
    assert len(result.issues) == 1
    assert "过长" in result.issues[0].reason


def test_parse_dedupes_within_batch() -> None:
    result = parse_import_text("逆袭\n逆袭", valid_categories=CATEGORIES)
    assert len(result.words) == 1
    assert result.duplicates == 1


def test_parse_same_word_in_different_category_kept() -> None:
    """同词不同分类不算重复（分类是词的一部分）。"""
    result = parse_import_text("themes:逆袭\ncharacters:逆袭", valid_categories=CATEGORIES)
    assert len(result.words) == 2
    assert result.duplicates == 0


def test_parse_default_category_used() -> None:
    result = parse_import_text("逆袭", default_category="plots", valid_categories=CATEGORIES)
    assert _words(result) == [("plots", "逆袭")]


def test_parse_keeps_line_numbers() -> None:
    result = parse_import_text("\n\n逆袭", valid_categories=CATEGORIES)
    assert result.words[0].line_no == 3


def test_resolve_category_known_and_unknown() -> None:
    assert resolve_category("themes", CATEGORIES) == "themes"
    assert resolve_category("THEMES", CATEGORIES) == "themes"
    assert resolve_category("主题", CATEGORIES) == "themes"
    assert resolve_category("不存在的分类", CATEGORIES) is None
    assert resolve_category("", CATEGORIES) is None


def test_resolve_category_without_valid_list() -> None:
    """不限制分类时，别名照样能解析。"""
    assert resolve_category("剧情") == "plots"
    assert resolve_category("法宝") == "items"


def test_category_aliases_cover_all_keys() -> None:
    """每个规范分类 key 都要有中文别名。"""
    keys = set(CATEGORY_ALIASES.values())
    assert keys == {"themes", "characters", "plots", "scenes", "items"}
