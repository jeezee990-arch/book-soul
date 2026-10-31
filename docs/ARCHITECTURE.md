# Book Soul 架构设计

> 文档面向贡献者，描述模块划分、数据流、关键设计决策。

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│  Tauri Desktop Shell (Rust)                              │
│  - 单窗口 WebView（Chromium 内核）                       │
│  - 启动后端进程（随机空闲端口）/ IPC 桥                  │
│  - 端口下发 + 就绪握手（前端不硬编码地址）                │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  React 18 + Vite (SPA)                                   │
│  - HashRouter（4 个一级页面：写作/开新书/素材库/设置）    │
│  - Zustand（7 个 store）                                 │
│  - shadcn/ui + Tailwind                                  │
└─────────────────────────────────────────────────────────┘
              │ fetch / SSE (ndjson) —— 流式不经过 Rust
              ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (async) + uvicorn                               │
│  - 16 个路由模块（novel / chapter / character / ...）    │
│  - 业务服务层 services/（26 个）                         │
│  - LLM 抽象层 core/llm/                                  │
│  - SQLAlchemy 2.0 + aiosqlite（外键约束已开启）          │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│  SQLite (本地文件 data/book-soul.db)                    │
│  + 7 张业务表（novels / chapters / characters / ...）   │
│  + 文件系统（data/secrets/、data/wordbanks/、logs/）      │
└─────────────────────────────────────────────────────────┘
```

> ⚠️ **没有 ChromaDB / 向量库** —— 早期设计里的 RAG 已移除：
> 对个人网文收益低（要 50+ 章才体现）、负担重（embedding 依赖 + 向量库 + 检索调优）。
> 当前用「人物卡 + 最近 3 章摘要 + 上一章尾部」的滑动窗口策略。

## 2. 目录分层

```
server/src/
├── api/         # 路由层（HTTP 接口、依赖注入、错误映射）—— 16 个模块
├── services/    # 业务逻辑（CRUD、生成、扫描、备份）—— 26 个
├── models/      # SQLAlchemy ORM（7 张表）
├── schemas/     # Pydantic（API 输入输出契约）
├── core/        # 基础设施
│   ├── llm/        # LLM 抽象（Provider Protocol + OpenAI 兼容 + Ollama）
│   │               #   + thinking（思考净身）/ cache（健康缓存）/ partial_json
│   ├── skills/     # Skill 系统（base / registry / manager / loader + builtin 12 个）
│   ├── security/   # dpapi / secret_store / encryption / keyring_manager
│   ├── scanner/    # 本地扫描
│   ├── versioning/ # 版本树 + diff
│   ├── chapter_context.py  # 章节 prompt + 上下文组装（单文件）
│   ├── prose_format.py     # 正文排版归一化（兜底断段 / 去空格 / 连续对白拆段）
│   ├── paths.py    # 路径解析统一入口（开发态 / 打包态）
│   ├── watchdog.py # 父进程看门狗（桌面端崩了后端自己退）
│   └── config.py / logging.py
└── db.py        # SQLAlchemy async engine + 通用补列 + 外键约束 + 孤儿清理
```

**铁律**：
- 业务逻辑在 `services/`，API 路由只做依赖注入 + 错误映射
- DB 操作走 `models/`，service 不写原生 SQL
- 文件 IO 集中在 service 层
- LLM 抽象在 `core/llm/`，业务不直接 import openai SDK
- 路径解析统一走 `core/paths.py`，禁止再写 `_find_repo_root()`

## 3. 数据模型

```
novels ──┬─── characters ─── character_versions
         │         (parent_version_id 自引用，链表)
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

### 级联语义（外键必须显式开启）

SQLite 的 `PRAGMA foreign_keys` **默认 OFF**，ORM 里的 `ondelete=` 不会生效 ——
删作品会留孤儿，而 SQLite 还会复用被删掉的 id，导致旧章节串进新作品。
`core/db.py` 在连接建立时开 pragma，并在启动时清理历史孤儿。

| 外键 | ondelete | 语义 |
|---|---|---|
| `chapters.novel_id` / `characters.novel_id` / `outlines.novel_id` | CASCADE | 删作品 → 连带删子行 |
| `chapter_versions.chapter_id` / `character_versions.character_id` | CASCADE | 删章节/人物 → 连带删版本 |
| `*_versions.parent_version_id` / `*.current_version_id` | SET NULL | 断链但保留数据 |
| `inspirations.novel_id` | SET NULL | **素材保留**，只脱离作品 |

详见 `server/src/models/`（ORM 定义）与 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) §3.4 数据层。

### 启动时的 schema 自愈

`init_db()` 依次做三件事，**任何一步失败都不阻断应用启动**：

1. `Base.metadata.create_all` —— 建缺失的表（只建表，不加列）
2. `_ensure_missing_columns` —— 从 ORM 元数据推导，ALTER 补上缺失的列
   （不硬编码表名；SQLite 加不了 PK/UNIQUE 列，NOT NULL 列必须有默认值）
3. `_purge_orphan_rows` —— 清"父行已删"的孤儿行（CASCADE 删行 / SET NULL 置空）

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
  summarize: ollama
```

业务代码不感知 provider，工厂 `create_llm_client_for_scene("chapter_generation")` 自动按路由解析。

## 5. 流式协议

**后端**：`StreamingResponse` + `application/x-ndjson`，每行一个 JSON。

单结果流（章节生成 / 重写）：
- 正文增量：`{"text": "..."}`
- 完成：`{"done": true, "provider": "...", "model": "..."}`
- 错误：`{"error": "..."}`（transport 类）

多版本流（剧情 / 大纲 / 人物卡）用 `event` 字段区分：
- `{"event": "thinking", "index": 1, "text": "..."}` —— 模型思考（**不能丢**）
- `{"event": "delta", "index": 1, "text": "..."}` —— 正文增量
- `{"event": "version_done", "index": 1, "summary": "..."}` —— 某版本完成
- `{"event": "error", "index": 1, "message": "..."}` —— 某版本失败
- `{"event": "done", "provider": ..., "model": ..., "elapsed_sec": ..., "first_delta_sec": ...}`

> **保序语义**：内容事件（thinking / delta）**实时透传**；
> 只有里程碑事件（`version_done` / `error`）按下标保序。
> 用 `merge_queue_events_milestone_ordered`，**不要**用严格保序版本
> （那是「队列 1 消费完才消费队列 2」，会让后面版本的内容憋到最后一口气涌出）。

**前端**（`apps/desktop/src/api/streams.ts`）：
- `fetch` + `ReadableStream.getReader()` + `TextDecoder` 按 `\n` 切
- `readNdjsonStream(path, options)` 异步生成 `StreamEvent`
- 调用方用 `for await` 消费
- **`detectStreamFailure(ev)` 必须用** —— transport 与 server 两类失败都要认，
  漏掉任何一类界面都会永远转圈

## 6. 关键设计决策

### 6.1 LLM 路由而不是硬编码
业务场景可独立配置 provider（如摘要走本地 ollama，章节生成走云端 mimo）。

### 6.2 正文排版归一化，而不是原样落库
LLM 返回的正文**不能原样存进编辑器** —— 模型爱犯三个毛病：
汉字被空格拆开（"山 门 前 的"）、不给段落、连续对白挤在一段。

所以 `core/prose_format.py::ProseFormatter` 做**增量**排版（边流边整理）：
去汉字间空格（保留英文单词间的）、`\n` → 段落分隔、**兜底断段**（≥30 字遇句末标点）、
**连续对白强制拆段**（`“甲？”“乙。”` → 两段，但 `将“沈”“砚”二字` 不拆 —— 引用不能拆断）。

配套的两条硬约定：

- **字数 = 非空白字符数**（`count_prose_words`），与 Word 的「字数」和网文平台一致。
  禁用 `len(text)` —— 会把换行符算进去，界面字数虚高。
- **前端 `countProseWords` 必须与后端完全一致**（JS 的 `\s` 不匹配全角空格 U+3000，
  要单独覆盖）。

前端插入也必须是**插进最后一个段落内部**，不能在文末 `insertText` ——
后者每次 flush 都新建一个段落，1012 个假段落把 3314 字撑成 5338 字。

详见 [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) §5.4。

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

### 6.8 大纲两阶段：先骨架，后补细节
阶段一 LLM 只出**卷章骨架**（便宜、快），阶段二**并行**给每卷补章节详情
（`summary` + `key_events`）。这样章节不再只有标题。

- 阶段二有**调用预算上限**（`MAX_CALLS_PER_VOLUME = 24`）：超预算的章节给占位概要
  （诚实标注「【待细化】」，**不编剧情**）
- 内容级失败走占位，**不报 volume_error**；系统级错误才上抛
- 失败不阻塞其他卷 —— 阶段二各卷独立结算

### 6.9 词库按板块分文件管理
`config/wordbanks/{dushi,xiuxian,xuanyi,yanqing}.yaml` —— 修仙的词不会出现在都市板块。
写盘位置：开发态落仓库 `config/wordbanks/`，打包态落 `<data_dir>/wordbanks/`。

## 7. 数据流：章节生成（典型场景）

```
User → 写作页 → "生成正文" 按钮
  ↓ POST /chapters/{id}/generate (user_prompt=本章要点, target_word_count)
  ↓
ChapterGenerator.stream_generate_parts(chapter_id, user_prompt, target_word_count)
  ↓ 加载 chapter / novel / characters
  ↓ get_chapter_outline(...) 取**本章大纲**
  │    ·作品有大纲 → 从 structure 里按章号定位（volumes[].chapters[] / 扁平 chapters[]）
  │    ·没有大纲   → 用 chapter.outline 字段
  ↓ select_relevant_characters(...) 只带**本章出场**人物卡
  ↓ 拼 prompt (chapter_generation.yaml)
  ↓ create_llm_client_for_scene("chapter_generation") → OpenAI 兼容
  ↓ ProseFormatter.feed(delta)  ★ 增量排版（去空格 / 兜底断段 / 连续对白拆段）
  ↓ AsyncIterator[(kind, text)]  kind ∈ {thinking, text}
  ↓
FastAPI StreamingResponse(ndjson)
  ↓ HTTP chunked transfer（前端直连 Python，不经过 Rust）
  ↓
前端 readNdjsonStream → classifyChapterStreamEvent
  ↓ for await 消费
  ↓ 正文 → prose-insert.ts 插进**最后一个段落内部**（Tiptap，不是文末新建段落）
  ↓ 思考 → "模型思考中…"面板（净身后的纯中文）
  ↓
完成 → PATCH /chapters/{id}/content (trigger=llm_generate)
  ↓ 取**编辑器全文**落库（不能用流式累积量 —— 生成是追加、重写是替换选区）
  ↓
DB: chapter.current_version_id = 新版本
```

## 8. 安全

- API Key 存储优先级：**环境变量 > DPAPI 加密文件（打包版默认）> 系统 Keyring**；
  明文永不落盘，打包版不含 `.env`
- SQLAlchemy ORM（防 SQL 注入）
- 路径检查（防 zip slip / 路径越界）
- 文件大小限制（备份 ≤500MB / 读文件 ≤5MB）
- API 输入 Pydantic 校验
- 章节字数硬限 1k-8k（唯一来源：`config/llm.yaml` 的 `chapter_limits`）
- context_window ≥ 32k 才能生成章节（`model_checker`）
- SQLite 外键约束已开启（见 §3）—— 删作品级联清理，不留孤儿

详见 [SECURITY.md](../SECURITY.md)。

## 9. 性能

| 指标 | 目标 | 实测 |
|---|---|---|
| 首字延迟 | 发起生成 → 首字符 ≤ 3s | 推理模型思考期可能 > 3s（思考内容会转发，不空窗） |
| 启动时间 | 双击 exe → UI 可交互 ≤ 5s | — |
| 流式转发开销 | 每 token ≤ 1ms | 实测 **0.5ms/token**（40 delta，间隔 50.6ms vs mock 50ms） |
| 章节生成 prompt | 只带**本章出场**人物卡 | `select_relevant_characters()`（一个都没匹配上时退回全部） |

- 后端 `asyncio.gather` 并行多版本 LLM 调用（剧情 / 大纲 / 人物卡）
- **流式链路不是瓶颈 —— 慢在模型**：别再优化"转发"环节，
  要优化的是模型选型、输出长度、思考时长
- 并行 LLM 调用 + **串行写库**：`AsyncSession` 不是并发安全的，
  并发 `flush()` 会抛 `Session is already flushing`（用 `asyncio.Lock` 或 for 循环）
- Tiptap 编辑器对长文档 O(n) per insert，Phase 9+ 优化
- 数据库单表 1k 章内无压力

## 10. 路线图（Phase 9+）

- [ ] Phase 9：协作编辑（WebSocket / Yjs CRDT）
- [ ] Phase 9：多模态（图像 / 音频输入）
- [ ] Phase 9：智能体（Agent）模式（自动多步任务）
- [ ] Phase 9：浏览器扩展（从网页提取灵感）
- [ ] Phase 9：移动端（Tauri Mobile）
