"""会话级对话记忆（Phase 1.7 真实现）。

设计：
- in-memory list（不持久化，会话结束即丢）
- 简单的 round-robin 截断：保留最后 N 轮（user + assistant 各算 1 轮）
- 接口稳定，Phase 4 可以替换底层（接 Redis / DB）而不用改调用方
"""

from __future__ import annotations

from typing import Literal

Role = Literal["system", "user", "assistant"]


class ConversationMemory:
    """会话级多轮对话历史。

    用法::

        mem = ConversationMemory(session_id="abc", max_turns=10)
        mem.add_user("你好")
        mem.add_assistant("你好！")
        msgs = mem.get_messages()  # 给 LLM
    """

    def __init__(self, session_id: str, max_turns: int = 20) -> None:
        if max_turns < 1:
            raise ValueError(f"max_turns must be >= 1, got {max_turns}")
        self.session_id = session_id
        self.max_turns = max_turns
        self._messages: list[dict[str, str]] = []

    def add_user(self, content: str) -> None:
        """追加一条 user 消息。"""
        self._append("user", content)

    def add_assistant(self, content: str) -> None:
        """追加一条 assistant 消息。"""
        self._append("assistant", content)

    def add_system(self, content: str) -> None:
        """追加一条 system 消息（不会被截断时丢掉，放在队首）。"""
        self._messages.append({"role": "system", "content": content})

    def add_message(self, role: Role, content: str) -> None:
        """通用追加（不限制 role）。"""
        if role not in ("system", "user", "assistant"):
            raise ValueError(f"Invalid role: {role!r}")
        self._append(role, content)

    def get_messages(self) -> list[dict[str, str]]:
        """返回当前所有消息的拷贝（调用方改不会影响内部状态）。"""
        return list(self._messages)

    def get_last_user_message(self) -> str | None:
        """返回最后一条 user 消息；没有则 None。"""
        for msg in reversed(self._messages):
            if msg["role"] == "user":
                return msg["content"]
        return None

    def clear(self) -> None:
        """清空（保留 system 消息）。"""
        self._messages = [m for m in self._messages if m["role"] == "system"]

    def truncate(self) -> None:
        """手动触发截断（保留 system + 最后 max_turns*2 条 user/assistant）。"""
        self._truncate()

    def __len__(self) -> int:
        return len(self._messages)

    def _append(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._truncate()

    def _truncate(self) -> None:
        """保留 system 消息 + 最后 max_turns*2 条 user/assistant。"""
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        other = [m for m in self._messages if m["role"] != "system"]
        max_other = self.max_turns * 2  # 每轮 2 条消息
        if len(other) > max_other:
            other = other[-max_other:]
        self._messages = system_msgs + other
