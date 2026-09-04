"""RAG 检索记忆（Phase 1.7 stub，Phase 4 接 ChromaDB）。

Phase 4 实现要点（备忘）：
- 用 ChromaDB 嵌入式存储（用户数据目录下的 chroma/）
- 文本先 embedding 再存；检索时 embed query → top-k 相似度
- 集合按 novel_id 分桶，避免跨作品串扰
- 支持 metadata 过滤（按 chapter / type / tag 过滤）
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from loguru import logger


class RagMemory:
    """RAG 检索记忆：基于向量相似度检索历史内容。

    Phase 1 stub：所有 add 返回 fake id，search 返回空 list。
    Phase 4 完善：接 ChromaDB。
    """

    def __init__(
        self,
        novel_id: int,
        *,
        collection: str = "default",
        persist_dir: str | None = None,
    ) -> None:
        self.novel_id = novel_id
        self.collection_name = collection
        self.persist_dir = persist_dir
        # Phase 4: 实际加载 chromadb.Client(persist_dir)

    async def add(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        """添加一段文本到检索库。

        Phase 1 stub：返回 fake id；Phase 4 调 chromadb.add。
        """
        rid = doc_id or f"stub-{uuid4().hex[:8]}"
        logger.debug(
            f"RagMemory.add stub: novel={self.novel_id}, "
            f"collection={self.collection_name}, id={rid}, len={len(text)}"
        )
        return rid

    async def search(
        self,
        query: str,
        *,
        k: int = 5,
        where_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """检索与 query 最相关的 k 条记录。

        Phase 1 stub：返回空 list；Phase 4 调 chromadb.query。

        返回格式：``[{"id": str, "text": str, "metadata": dict, "distance": float}]``
        """
        logger.debug(
            f"RagMemory.search stub: novel={self.novel_id}, "
            f"collection={self.collection_name}, q={query[:30]!r}, k={k}"
        )
        return []

    async def delete(self, doc_id: str) -> None:
        """按 id 删除一条。Phase 1 no-op。"""
        logger.debug(f"RagMemory.delete stub: id={doc_id}")

    async def clear(self) -> None:
        """清空 collection。Phase 1 no-op；Phase 4 用 chromadb 删 collection。"""
        logger.debug(f"RagMemory.clear stub: collection={self.collection_name}")
