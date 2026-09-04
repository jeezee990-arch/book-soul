"""项目级记忆（Phase 1.7 stub，Phase 4 接实际存储）。

接口设计原则：
- 方法签名在 Phase 1 就定好，后续只换实现不换 API
- Phase 1 返回空数据，调用方不会因 stub 而崩溃
- 异步签名（async）让 Phase 4 接 DB / 远端存储时不用改调用方
"""

from __future__ import annotations

from loguru import logger


class ProjectMemory:
    """项目级记忆：作品的全局上下文。

    Phase 1 stub：所有方法返回空数据 / no-op。
    Phase 4 完善：从 DB 聚合作品的人物/章节摘要/大纲/灵感，构造完整 prompt 上下文。
    """

    def __init__(self, novel_id: int) -> None:
        self.novel_id = novel_id

    async def get_context(self) -> dict:
        """获取作品完整上下文（人物/章节摘要/大纲/设定）。

        Phase 1 返回空 dict；Phase 4 返回结构化 dict。
        """
        logger.debug(f"ProjectMemory.get_context stub for novel={self.novel_id}")
        return {}

    async def add_note(self, key: str, value: str) -> None:
        """添加一条项目级笔记（如"主角弱点是 X"）。

        Phase 1 no-op；Phase 4 存到项目笔记表（v1.7 没建表）。
        """
        logger.debug(f"ProjectMemory.add_note stub: novel={self.novel_id}, key={key}")

    async def get_notes(self) -> dict[str, str]:
        """获取所有项目笔记。

        Phase 1 返回空 dict；Phase 4 从 notes 表读。
        """
        return {}

    async def clear(self) -> None:
        """清空项目记忆（测试用）。Phase 1 no-op。"""
        pass
