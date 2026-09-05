# Book Soul 架构设计

> 文档面向贡献者，描述模块划分、数据流、关键设计决策。

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│  Tauri Desktop Shell (Rust)                              │
│  - 单窗口 WebView（Chromium 内核）                       │
│  - 启动后端进程 / IPC 桥                                  │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  React 18 + Vite (SPA)                                   │
│  - HashRouter（5 个主页面）                              │
│  - Zustand（轻状态） / TanStack Query 风格手写            │
│  - shadcn/ui + Tailwind                                   │
└─────────────────────────────────────────────────────────┘
              │ fetch / SSE (ndjson)
              ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (async) + uvicorn                               │
│  - 11 个路由模块（novel / chapter / character / ...）    │
│  - 业务服务层 services/                                  │
│  - LLM 抽象层 core/llm/                                  │
│  - SQLAlchemy 2.0 + aiosqlite                            │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  SQLite (本地文件 data/book-soul.db)                    │
│  + ChromaDB（向量库，预留 Phase 9+）                     │
│  + 文件系统（data/novels/、logs/）                       │
└─────────────────────────────────────────────────────────┘
```

## 2. 目录分层

```
server/src/
├── api/         # 路由层（HTTP 接口、依赖注入、错误映射）
├── services/    # 业务逻辑（CRUD、生成、扫描、备份）
├── models/      # SQLAlchemy ORM（数据表）
├── schemas/     # Pydantic（API 输入输出契约）
├── core/        # 基础设施
│   ├── llm/        # LLM 抽象（Provider Protocol + OpenAI 兼容实现 + Ollama）
│   ├── quality/    # 质检 prompt 加载
│   ├── chapter_context/  # 章节生成 prompt + 上下文
│   ├── scanner/    # 本地扫描（detector / scanner / importer）
│   └── skills/     # Skill 系统（base / registry / builtin 12 个）
└── db.py        # SQLAlchemy async engine
```

**铁律**：
- 业务逻辑在 `services/`，API 路由只做依赖注入 + 错误映射
- DB 操作走 `models/`，service 不写原生 SQL
- 文件 IO 集中在 service 层
- LLM 抽象在 `core/llm/`，业务不直接 import openai SDK

## 3. 数据模型

```
novels ──┬─── characters ─── character_versions
         │
         ├─── outlines
         │
         ├─── chapters ─── chapter_versions
         │         │
         │         └─── (parent_version_id 自引用，链表)
         │
         └─── inspirations (FK novels.id, nullable)

inspirations  (独立：通用灵感 novel_id=NULL；关联灵感 FK)
```

详见 `server/src/models/`。

## 4. LLM 抽象

**核心接口**（`server/src/core/llm/base.py`）：
```python
class BaseLLMClient(Protocol):
    provider: str
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[str]: ...
```

**实现**：
- `OpenAICompatClient`（httpx 手写，支持 mimo / minimax / OpenAI / 任何 OpenAI 兼容 API）
- `OllamaClient`（Ollama /v1 协议，本地）

**路由**（`config/llm.yaml`）：每个业务场景可独立配置 provider
```yaml
routing:
  chapter_generation: mimo
  chapter_rewrite: mimo
  quality_check: ollama
```

业务代码不感知 provider，工厂 `create_llm_client_for_scene("chapter_generation")` 自动按路由解析。

## 5. 流式协议

**后端**：`StreamingResponse` + `application/x-ndjson`，每行一个 JSON：
- 增量：`{"text": "..."}`
- 完成：`{"done": true, "provider": "...", "model": "..."}`
- 错误：`{"error": "..."}`

**前端**（`apps/desktop/src/api/streams.ts`）：
- `fetch` + `ReadableStream.getReader()` + `TextDecoder` 按 `\n` 切
- `readNdjsonStream(path, options)` 异步生成 `StreamEvent`
- 调用方用 `for await` 消费

## 6. 关键设计决策

### 6.1 LLM 路由而不是硬编码
业务场景可独立配置 provider（如质检走本地 ollama，章节生成走云端 mimo）。

### 6.2 不存中间结果
质检报告**不存 DB**（Phase 5 简化）。Phase 6.2 藏书馆再补 `quality_reports` 表。

### 6.3 版本控制用软回滚
每次"回滚"**生成新版本**而不是物理改原版本。完整审计链。

### 6.4 Diff 用 difflib 而非 diff-match-patch
Phase 4.6 暂用标准库。中文场景精度可能不够，未来升级。

### 6.5 导入章节 trigger="imported"
`chapter_status` 加了 `"imported"`，区分原创 vs 扫描导入。

### 6.6 Skill 系统是同步协议的
`Skill` Protocol + `SkillResult` dataclass，所有 builtin 不依赖 LLM（除 web_search 占位）。

### 6.7 备份不重启服务
导入备份后**不重启** Tauri（SQLite 连接池已建立）。前端弹 toast 提示用户手动重启。

## 7. 数据流：章节生成（典型场景）

```
User → Creation 页 → "流式生成" 按钮
  ↓ POST /chapters/{id}/generate (user_prompt, target_word_count)
  ↓
ChapterGenerator.stream_generate(chapter_id, user_prompt)
  ↓ 加载 chapter / novel / characters / outline
  ↓ 拼 prompt (chapter_generation.yaml)
  ↓ create_llm_client_for_scene("chapter_generation") → mimo OpenAI 兼容
  ↓ AsyncIterator[str] (delta chunks)
  ↓
FastAPI StreamingResponse(ndjson)
  ↓ HTTP chunked transfer
  ↓
前端 readNdjsonStream
  ↓ for await 消费
  ↓ editorRef.appendText(text) → Tiptap 末尾插入
  ↓
完成 → PATCH /chapters/{id}/content (trigger=llm_generate)
  ↓
DB: chapter.current_version_id = 新版本
```

## 8. 安全

- API Key 存系统 keyring（不存 .env）
- SQLAlchemy ORM（防 SQL 注入）
- 路径检查（防 zip slip / 路径越界）
- 文件大小限制（备份 ≤500MB / 读文件 ≤5MB）
- API 输入 Pydantic 校验
- 章节字数硬限 1k-8k
- context_window ≥ 32k 才能生成章节（`model_checker`）

详见 [SECURITY.md](../SECURITY.md)。

## 9. 性能

- 后端 `asyncio.gather` 并行 5 维度质检（~30s）
- 流式响应首字延迟 5-15s（mimo）
- Tiptap 编辑器对长文档不友好（O(n) per insert），Phase 9+ 优化
- 数据库单表 1k 章内无压力

## 10. 路线图（Phase 9+）

- [ ] Phase 9：协作编辑（WebSocket / Yjs CRDT）
- [ ] Phase 9：多模态（图像 / 音频输入）
- [ ] Phase 9：智能体（Agent）模式（自动多步任务）
- [ ] Phase 9：浏览器扩展（从网页提取灵感）
- [ ] Phase 9：移动端（Tauri Mobile）
