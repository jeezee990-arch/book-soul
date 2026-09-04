"""Memory 子包（Phase 1.7 骨架，Phase 4 完善）。

- ``ProjectMemory``：项目级上下文（作品/人物/剧情/设定的全局快照），用于 LLM prompt 构造
- ``RagMemory``：基于向量相似度检索的历史内容（Phase 4 接 ChromaDB）
- ``ConversationMemory``：会话级多轮对话历史（in-memory list，Phase 1 已可用）
"""
