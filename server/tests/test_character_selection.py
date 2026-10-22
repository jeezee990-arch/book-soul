"""人物卡筛选（select_relevant_characters）单元测试。

目的：保证"只给本章出场人物"这个优化不会让角色凭空消失，
也不会误删主角 / 主角团。
"""

from __future__ import annotations

from src.core.chapter_context import select_relevant_characters
from src.models.character import Character


def _char(name: str, role: str = "其他", cid: int = 0) -> Character:
    return Character(id=cid, novel_id=1, name=name, role=role)


def test_empty_list_returns_empty() -> None:
    assert select_relevant_characters([], "任意上下文") == []


def test_empty_context_returns_all() -> None:
    """上下文为空 → 全部返回（不要凭空筛掉角色）。"""
    chars = [_char("甲", "反派", 1), _char("乙", "其他", 2)]
    assert select_relevant_characters(chars, "") == chars
    assert select_relevant_characters(chars, "   ") == chars


def test_keeps_character_named_in_context() -> None:
    """名字出现在上下文里 → 保留。"""
    chars = [_char("林渊", "其他", 1), _char("苏清", "其他", 2)]
    result = select_relevant_characters(chars, "林渊在山门前拔剑")
    assert [c.name for c in result] == ["林渊"]


def test_always_keeps_protagonist_even_if_not_in_context() -> None:
    """主角 / 主角团永远保留（即使上下文里没提到）。"""
    chars = [
        _char("林渊", "主角", 1),
        _char("苏清", "主角团", 2),
        _char("赵无极", "反派", 3),
    ]
    result = select_relevant_characters(chars, "无关内容")
    names = [c.name for c in result]
    assert "林渊" in names
    assert "苏清" in names
    assert "赵无极" not in names


def test_combines_protagonist_and_mentioned() -> None:
    """主角 + 上下文提到的角色 都要保留。"""
    chars = [
        _char("林渊", "主角", 1),
        _char("苏清", "其他", 2),
        _char("赵无极", "反派", 3),
    ]
    result = select_relevant_characters(chars, "赵无极出手了")
    names = {c.name for c in result}
    assert names == {"林渊", "赵无极"}


def test_no_match_falls_back_to_all() -> None:
    """一个都没匹配上（且没有主角）→ 退回全部，宁多勿少。"""
    chars = [_char("甲", "反派", 1), _char("乙", "其他", 2)]
    result = select_relevant_characters(chars, "完全无关的文本")
    assert len(result) == 2


def test_does_not_duplicate() -> None:
    """主角同时出现在上下文里 → 不应重复。"""
    chars = [_char("林渊", "主角", 1)]
    result = select_relevant_characters(chars, "林渊出场")
    assert len(result) == 1
    assert result[0].name == "林渊"


def test_preserves_original_order() -> None:
    """保持原始顺序（主角优先的插入顺序不影响 list 内的相对次序）。"""
    chars = [
        _char("甲", "其他", 1),
        _char("林渊", "主角", 2),
        _char("乙", "其他", 3),
    ]
    result = select_relevant_characters(chars, "乙和甲")
    names = [c.name for c in result]
    assert names == ["林渊", "甲", "乙"]
