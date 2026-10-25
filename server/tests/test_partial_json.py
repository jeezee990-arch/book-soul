"""半截 JSON 容错解析测试（2026-10-25 新增）。

用途：大纲生成返回一个大 JSON（20-40 章）。流式传输时用户拿到的是"半截
JSON"——旧实现把原始 JSON 文本直接丢给前端用 ``<pre>`` 渲染，用户看到的
是一堆英文代码。

要显示中文剧情，就必须在流式过程中把**已经写完的部分**解析出来。
:func:`parse_partial_json` 负责这件事。
"""

from __future__ import annotations

from src.core.llm.partial_json import parse_partial_json


def test_complete_json_parses_directly() -> None:
    """完整 JSON 直接解析。"""
    obj = parse_partial_json('{"volumes": [{"name": "第一卷"}], "overall_theme": "主题"}')
    assert obj is not None
    assert obj["volumes"][0]["name"] == "第一卷"
    assert obj["overall_theme"] == "主题"


def test_partial_json_extracts_finished_volume() -> None:
    """第一个卷写完了 → 能提取出来（虽然整个 JSON 还没结束）。"""
    raw = (
        '{"volumes": ['
        '{"name": "第一卷 觉醒", "summary": "主角觉醒。", '
        '"chapters": [{"title": "第一章 变故", "summary": "家族被灭。", '
        '"key_events": ["夜袭", "逃生"]}]},'
    )
    obj = parse_partial_json(raw)
    assert obj is not None
    volumes = obj["volumes"]
    assert len(volumes) == 1
    assert volumes[0]["name"] == "第一卷 觉醒"
    assert volumes[0]["chapters"][0]["title"] == "第一章 变故"
    assert volumes[0]["chapters"][0]["key_events"] == ["夜袭", "逃生"]


def test_partial_json_drops_incomplete_tail() -> None:
    """最后半个对象没写完 → 只保留完整的部分。"""
    raw = (
        '{"volumes": ['
        '{"name": "第一卷", "chapters": [{"title": "第一章"}]},'
        '{"name": "第二卷", "chapters": [{"titl'
    )
    obj = parse_partial_json(raw)
    assert obj is not None
    volumes = obj["volumes"]
    assert len(volumes) == 1
    assert volumes[0]["name"] == "第一卷"


def test_partial_json_returns_none_when_nothing_complete() -> None:
    """连一个完整字段都没写完 → None（不是异常）。"""
    assert parse_partial_json('{"volumes": [{"name": "第一') is None
    assert parse_partial_json("") is None
    assert parse_partial_json("完全没有 JSON") is None


def test_partial_json_handles_leading_noise() -> None:
    """LLM 常在 JSON 前面加"以下是..."，要从第一个 ``{`` 开始找。"""
    raw = '以下是生成的大纲：\n{"volumes": [{"name": "第一卷", "chapters": []}]}'
    obj = parse_partial_json(raw)
    assert obj is not None
    assert obj["volumes"][0]["name"] == "第一卷"


def test_partial_json_ignores_braces_inside_strings() -> None:
    """字符串里的括号不能当成 JSON 结构符号。"""
    raw = '{"volumes": [{"name": "第一卷 {括号}", "chapters": []}]'
    obj = parse_partial_json(raw)
    assert obj is not None
    assert obj["volumes"][0]["name"] == "第一卷 {括号}"


def test_partial_json_handles_escaped_quotes() -> None:
    """转义引号不能打断字符串状态。"""
    raw = '{"volumes": [{"name": "他说\\"你好\\"", "chapters": []}]'
    obj = parse_partial_json(raw)
    assert obj is not None
    assert obj["volumes"][0]["name"] == '他说"你好"'


def test_partial_json_handles_escaped_backslash() -> None:
    """转义反斜杠不能打断字符串状态。"""
    raw = '{"volumes": [{"name": "path C:\\\\temp", "chapters": []}]'
    obj = parse_partial_json(raw)
    assert obj is not None
    assert obj["volumes"][0]["name"] == "path C:\\temp"


def test_partial_json_nested_arrays_inside_chapters() -> None:
    """章里的数组字段（key_events）也要正确处理。"""
    raw = (
        '{"volumes": [{"name": "第一卷", "chapters": ['
        '{"title": "第一章", "key_events": ["a", "b", "c"]}'
    )
    obj = parse_partial_json(raw)
    assert obj is not None
    chapters = obj["volumes"][0]["chapters"]
    assert chapters[0]["key_events"] == ["a", "b", "c"]


def test_partial_json_non_dict_payload_returns_none() -> None:
    """顶层不是对象（比如是个数组）→ None。"""
    assert parse_partial_json("[1, 2, 3]") is None
