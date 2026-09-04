"""开新书三步流程状态机（Phase 3.7）。

按 PROJECT_PLAN.md v1.2 定义的 v1.2 流程：

  idle → keyword_step → plot_step → outline_step → character_step
                                                       ↓
                                                  edit_characters ⇄ character_step
                                                       ↓
                                                     save → done
                                                     save → keyword_step（再开一本）

不做的事：
- 不持久化（内存态；调用方按需 snapshot/restore）
- 不调 service/LLM（只管状态 + context；副作用在调用 transition 时做）
"""

from __future__ import annotations

from typing import ClassVar

from .state_machine import StateMachine


class NewBookStateMachine(StateMachine):
    """开新书流程状态机。"""

    # v1.2 流程：与"灵感园三步分页"对齐
    STATES: ClassVar[tuple[str, ...]] = (
        "idle",
        "keyword_step",
        "plot_step",
        "outline_step",
        "character_step",
        "edit_characters",
        "save",
        "done",
    )

    TRANSITIONS: ClassVar[dict[str, tuple[str, ...]]] = {
        "idle": ("keyword_step",),
        "keyword_step": ("plot_step",),  # 保存关键词卡片后
        "plot_step": (
            "keyword_step",  # 可回上步重选
            "outline_step",  # 进入大纲
        ),
        "outline_step": (
            "plot_step",  # 可回上步换剧情卡
            "character_step",  # 进入人物卡
        ),
        "character_step": (
            "edit_characters",
            "save",  # 直接保存
        ),
        "edit_characters": (
            "character_step",  # 返回
            "save",  # 完成编辑保存
        ),
        "save": (
            "done",  # 结束
            "keyword_step",  # 再开一本
        ),
        "done": (),  # 终态
    }

    # 状态标签（前端显示用）
    LABELS: ClassVar[dict[str, str]] = {
        "idle": "未开始",
        "keyword_step": "第一步 · 灵感词",
        "plot_step": "第二步 · 剧情",
        "outline_step": "第三步 · 大纲",
        "character_step": "第四步 · 人物卡",
        "edit_characters": "调整人物卡",
        "save": "保存中",
        "done": "完成",
    }

    def __init__(self, session_id: str = "", **initial_context: object) -> None:
        super().__init__(initial="idle", session_id=session_id, **initial_context)

    @property
    def session_id(self) -> str:
        return str(self.context.get("session_id", "") or "")

    @property
    def label(self) -> str:
        return self.LABELS.get(self.current_state, self.current_state)
