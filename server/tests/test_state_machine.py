"""状态机单元测试（Phase 3.7）。

覆盖：
- 通用 StateMachine 基类：转移合法/非法、context 合并、allowed_next、is_terminal
- NewBookStateMachine：v1.2 三步流程 + 状态回退 + 再开一本
- InvalidTransitionError / ValueError
- snapshot / reset
"""

from __future__ import annotations

import pytest

from src.core.workflow.new_book import NewBookStateMachine
from src.core.workflow.state_machine import (
    InvalidTransitionError,
    StateMachine,
)

# ===== 通用 StateMachine 基类 =====


class _DemoMachine(StateMachine):
    STATES = ("start", "middle", "end")
    TRANSITIONS = {
        "start": ("middle",),
        "middle": ("end", "start"),  # 允许回退
        "end": (),  # 终态
    }


def test_state_machine_initial_default() -> None:
    m = _DemoMachine()
    assert m.current_state == "start"
    assert m.context == {}


def test_state_machine_initial_with_context() -> None:
    m = _DemoMachine(foo="bar", n=42)
    assert m.current_state == "start"
    assert m.context == {"foo": "bar", "n": 42}


def test_state_machine_valid_transition() -> None:
    m = _DemoMachine()
    m.transition("middle")
    assert m.current_state == "middle"


def test_state_machine_transition_with_context() -> None:
    m = _DemoMachine()
    m.transition("middle", data="x", n=1)
    assert m.current_state == "middle"
    assert m.context == {"data": "x", "n": 1}


def test_state_machine_transition_context_overrides() -> None:
    m = _DemoMachine(x=1)
    m.transition("middle", x=2, y=3)
    assert m.context == {"x": 2, "y": 3}  # x 被覆盖


def test_state_machine_invalid_transition_raises() -> None:
    m = _DemoMachine()
    with pytest.raises(InvalidTransitionError) as exc_info:
        m.transition("end")  # start -> end 非法
    assert "start -> end" in str(exc_info.value)


def test_state_machine_unknown_state_raises() -> None:
    m = _DemoMachine()
    with pytest.raises(ValueError):
        m.transition("nonexistent")


def test_state_machine_can_transition() -> None:
    m = _DemoMachine()
    assert m.can_transition("middle") is True
    assert m.can_transition("end") is False


def test_state_machine_allowed_next() -> None:
    m = _DemoMachine()
    assert m.allowed_next() == ("middle",)
    m.transition("middle")
    assert m.allowed_next() == ("end", "start")


def test_state_machine_is_terminal() -> None:
    m = _DemoMachine()
    assert m.is_terminal() is False
    m.transition("middle")
    assert m.is_terminal() is False
    m.transition("end")
    assert m.is_terminal() is True


def test_state_machine_reset() -> None:
    m = _DemoMachine(foo="bar")
    m.transition("middle", x=1)
    m.reset()
    assert m.current_state == "start"
    assert m.context == {}


def test_state_machine_reset_with_initial() -> None:
    m = _DemoMachine()
    m.transition("middle")
    m.reset(initial="middle")
    assert m.current_state == "middle"


def test_state_machine_snapshot() -> None:
    m = _DemoMachine(foo="bar")
    m.transition("middle", n=1)
    snap = m.snapshot()
    assert snap == {"current_state": "middle", "context": {"foo": "bar", "n": 1}}
    # snapshot 是 dict 副本，不影响原 state
    assert m.current_state == "middle"


def test_state_machine_must_declare_states() -> None:
    class _Empty(StateMachine):
        pass

    with pytest.raises(TypeError):
        _Empty()


def test_state_machine_invalid_initial_state() -> None:
    class _M(StateMachine):
        STATES = ("a", "b")
        TRANSITIONS = {"a": ("b",), "b": ()}

    with pytest.raises(ValueError):
        _M(initial="z")


def test_state_machine_repr() -> None:
    m = _DemoMachine(foo="bar")
    r = repr(m)
    assert "_DemoMachine" in r
    assert "start" in r


# ===== NewBookStateMachine：v1.2 三步流程 =====


def test_new_book_initial_state() -> None:
    m = NewBookStateMachine(session_id="abc")
    assert m.current_state == "idle"
    assert m.session_id == "abc"
    assert m.context == {"session_id": "abc"}


def test_new_book_states_count() -> None:
    """v1.2 流程必须有 8 个状态（含 done 终态）。"""
    assert len(NewBookStateMachine.STATES) == 8
    assert "done" in NewBookStateMachine.STATES


def test_new_book_full_happy_path() -> None:
    m = NewBookStateMachine()
    assert m.current_state == "idle"
    m.transition("keyword_step", selected_genre="修仙")
    m.transition("plot_step", plots=["p1", "p2"])
    m.transition("outline_step", outline={"volumes": []})
    m.transition("character_step", novel_id=42)
    m.transition("save")
    m.transition("done")
    assert m.current_state == "done"
    assert m.is_terminal() is True


def test_new_book_can_go_back_keyword_to_plot() -> None:
    """从 plot 回到 keyword 重选。"""
    m = NewBookStateMachine()
    m.transition("keyword_step")
    m.transition("plot_step")
    m.transition("keyword_step")  # 回退
    assert m.current_state == "keyword_step"


def test_new_book_can_go_back_plot_to_keyword_invalid() -> None:
    """plot → keyword 合法（可回退）。"""
    m = NewBookStateMachine()
    m.transition("keyword_step")
    m.transition("plot_step")
    assert m.can_transition("keyword_step") is True


def test_new_book_invalid_skip_keyword_to_outline() -> None:
    """idle → outline 非法（必须先经过 keyword_step）。"""
    m = NewBookStateMachine()
    with pytest.raises(InvalidTransitionError):
        m.transition("outline_step")


def test_new_book_invalid_skip_plot_to_character() -> None:
    """outline → character 合法，但 plot → character 非法。"""
    m = NewBookStateMachine()
    m.transition("keyword_step")
    m.transition("plot_step")
    with pytest.raises(InvalidTransitionError):
        m.transition("character_step")


def test_new_book_edit_characters_round_trip() -> None:
    """character_step ⇄ edit_characters 双向。"""
    m = NewBookStateMachine()
    m.transition("keyword_step")
    m.transition("plot_step")
    m.transition("outline_step")
    m.transition("character_step")
    m.transition("edit_characters")
    assert m.current_state == "edit_characters"
    m.transition("character_step")
    assert m.current_state == "character_step"


def test_new_book_done_is_terminal() -> None:
    m = NewBookStateMachine()
    for s in [
        "keyword_step",
        "plot_step",
        "outline_step",
        "character_step",
        "save",
        "done",
    ]:
        m.transition(s)
    assert m.current_state == "done"
    assert m.is_terminal() is True


def test_new_book_save_can_restart() -> None:
    """save → done 或 save → keyword_step（再开一本）。"""
    m = NewBookStateMachine()
    m.transition("keyword_step")
    m.transition("plot_step")
    m.transition("outline_step")
    m.transition("character_step")
    m.transition("save")
    assert m.can_transition("done") is True
    assert m.can_transition("keyword_step") is True
    m.transition("keyword_step")  # 再开一本
    assert m.current_state == "keyword_step"


def test_new_book_label_property() -> None:
    m = NewBookStateMachine()
    assert m.label == "未开始"
    m.transition("keyword_step")
    assert "灵感词" in m.label
    m.transition("plot_step")
    assert "剧情" in m.label


def test_new_book_session_id_empty_default() -> None:
    m = NewBookStateMachine()
    assert m.session_id == ""


def test_new_book_context_accumulates() -> None:
    m = NewBookStateMachine(session_id="s1")
    m.transition("keyword_step", genre="修仙", keywords=["k1"])
    m.transition("plot_step", plots=["p1"])
    assert m.context["session_id"] == "s1"
    assert m.context["genre"] == "修仙"
    assert m.context["keywords"] == ["k1"]
    assert m.context["plots"] == ["p1"]


def test_new_book_snapshot() -> None:
    m = NewBookStateMachine(session_id="s1")
    m.transition("keyword_step", genre="修仙")
    snap = m.snapshot()
    assert snap["current_state"] == "keyword_step"
    assert snap["context"]["session_id"] == "s1"
    assert snap["context"]["genre"] == "修仙"
