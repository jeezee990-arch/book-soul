"""通用状态机基类（Phase 3.7）。

设计：
- 声明式 STATES + TRANSITIONS
- transition(to, **context) 校验合法转移
- 持有 context dict 累计状态数据
- 不持久化（内存态；持久化由调用方在 transfer 时自己存）

不做的事：
- 不做并发控制（一个状态机一个调用方；并发由外部加锁）
- 不做事件触发（纯 push 模型；事件订阅是上层职责）
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar


class InvalidTransitionError(ValueError):
    """状态转移非法（当前状态不允许转移到目标）。"""


class StateMachine:
    """通用状态机基类。

    子类声明 ``STATES``（全部状态名）+ ``TRANSITIONS``（dict[from, list[to]]）；
    实例化时 ``current_state`` 默认为 ``STATES[0]``（必须是 idle / 起点）。
    """

    STATES: ClassVar[tuple[str, ...]] = ()
    TRANSITIONS: ClassVar[Mapping[str, tuple[str, ...] | list[str]]] = {}

    def __init__(self, *, initial: str | None = None, **initial_context: object) -> None:
        if not self.STATES:
            raise TypeError(f"{type(self).__name__} must declare STATES before instantiation")
        start = initial or self.STATES[0]
        if start not in self.STATES:
            raise ValueError(f"initial state {start!r} not in STATES {self.STATES}")
        self.current_state: str = start
        self.context: dict[str, object] = dict(initial_context)

    # ===== 查询 =====
    def can_transition(self, to: str) -> bool:
        """判断当前状态能否转移到 to（不抛异常）。"""
        return to in self.TRANSITIONS.get(self.current_state, ())

    def allowed_next(self) -> tuple[str, ...]:
        """返回当前状态可转移到的目标状态列表。"""
        return tuple(self.TRANSITIONS.get(self.current_state, ()))

    def is_terminal(self) -> bool:
        """当前状态无后继转移 → 终态。"""
        return len(self.allowed_next()) == 0

    # ===== 转移 =====
    def transition(self, to: str, **context: object) -> None:
        """转移到目标状态，并把 context 合并到 self.context（覆盖式）。

        :raises InvalidTransitionError: 当前状态不允许转移到 to
        """
        if to not in self.STATES:
            raise ValueError(f"Unknown target state {to!r}; valid: {self.STATES}")
        if to not in self.allowed_next():
            raise InvalidTransitionError(
                f"Invalid transition: {self.current_state} -> {to}; "
                f"allowed from {self.current_state}: {self.allowed_next()}"
            )
        self.current_state = to
        if context:
            self.context.update(context)

    def reset(self, *, initial: str | None = None) -> None:
        """重置到起点状态，清空 context。"""
        start = initial or self.STATES[0]
        self.current_state = start
        self.context.clear()

    def snapshot(self) -> dict[str, object]:
        """当前状态的纯 dict 快照（用于持久化/序列化）。"""
        return {
            "current_state": self.current_state,
            "context": dict(self.context),
        }

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} state={self.current_state!r} "
            f"context_keys={list(self.context.keys())}>"
        )
