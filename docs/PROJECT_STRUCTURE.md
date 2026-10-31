# Book Soul 项目结构详解

> 面向贡献者与二次开发者。
> 想知道「改某个功能该动哪个文件」，看 [§6 修改指引](#6-修改指引)。
> 想知道「数据怎么流」，看 [§5 数据流](#5-数据流)。

---

## 1. 全局视图

```
┌────────────────────────────────────────────────────────────┐
│  Tauri 桌面壳（Rust）                                       │
│  src-tauri/src/                                            │
│  · main.rs        进程入口                                 │
│  · lib.rs         Tauri command / 窗口事件 / 应用装配       │
│  · sidecar.rs     后端定位与拉起：随机空闲端口 / 数据目录      │
│  · logging.rs     桌面端日志（release 无控制台 → 写文件）     │
└──────────────────────────┬─────────────────────────────────┘
                           │ invoke（一次性 IPC）
                           ▼
┌────────────────────────────────────────────────────────────┐
│  React 18 + Vite（SPA，HashRouter）                          │
│  apps/desktop/src/                                          │
│  · pages/      4 个一级页面                                  │
│  · components/ 通用组件 + shadcn/ui 原子组件                  │
│  · api/        后端 API 的 TS 客户端（16 个模块）             │
│  · stores/     Zustand（7 个 store）                        │
└──────────────────────────┬─────────────────────────────────┘
                           │ fetch / NDJSON 流（**不经过 Rust**）
                           ▼
┌────────────────────────────────────────────────────────────┐
│  FastAPI（async）+ uvicorn                                  │
│  server/src/                                                │
│  · api/       路由层：依赖注入 + 错误映射（16 个模块）        │
│  · services/  业务逻辑（26 个模块）                          │
│  · core/      基础设施：llm / skills / security / scanner …  │
│  · models/    SQLAlchemy 2 ORM（7 张表）                     │
│  · schemas/   Pydantic 契约（7 个模块）                      │
└──────────────────────────┬─────────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────────┐
│  SQLite：data/book-soul.db                                  │
│  + 文件系统：data/secrets/、data/wordbanks/、data/logs/       │
└────────────────────────────────────────────────────────────┘
```

**关键约束**

| 约束 | 原因 |
|---|---|
| 流式**不经过 Rust** | Tauri `invoke` 是一次性调用，做不了流式转发；前端直连 Python |
| 前端**不硬编码**后端地址 | 端口由 Rust 侧随机分配后下发（`get_backend_url`） |
| 后端路径**只走** `core/paths.py` | 打包后没有 `pyproject.toml`，向上找目录必然失败；`paths.py` 处理 `sys._MEIPASS` |
| 业务**不直接 import** httpx / LLM SDK | 换 provider 应该只是一行 YAML 改动 |

---

## 2. 前端 `apps/desktop/`

### 2.1 页面层 `src/pages/`

```
pages/
├── Writing/              # ✍️ 写作（/）
│   ├── index.tsx         # 三栏布局主容器
│   ├── chapter-tree.tsx  # 左栏：章节树 244px
│   ├── editor-pane.tsx   # 中栏：纸感编辑区（Tiptap）
│   ├── context-panel.tsx # 右栏：Tab 容器 332px
│   ├── ui.tsx            # 本页共享的小组件
│   ├── types.ts
│   ├── use-chapter-stream.ts  # ★ 章节流式消费（13.5 KB，写作页的流式核心）
│   └── tabs/             # 右栏 5 个 Tab，一个 Tab 一个文件
│       ├── generate-tab.tsx   # 生成
│       ├── rewrite-tab.tsx    # 重写（选区）
│       ├── character-tab.tsx  # 人物
│       ├── outline-tab.tsx    # 大纲（22.7 KB，本页最重）
│       └── version-tab.tsx    # 版本
│
├── NewBook/              # 🆕 开新书（/new）—— 三步向导
│   ├── index.tsx         # 向导容器（18.4 KB）
│   ├── seed-step.tsx     # 第 1 步：种子
│   ├── novel-name-field.tsx  # ★ 书名输入框 + 重名提示（前后端同名规则一致）
│   ├── plot-step.tsx     # 第 2 步：剧情
│   ├── outline-step.tsx  # 第 3 步：大纲与人物（17.3 KB）
│   ├── use-newbook-flow.ts    # 三步状态编排（由 Zustand 承载）
│   ├── use-plot-stream.ts     # ★ 剧情流（3 个版本并行）
│   ├── use-outline-stream.ts  # ★ 大纲流
│   ├── use-character-stream.ts# ★ 人物卡流
│   ├── wordbank-manager-*.tsx # 词库管理（列表 / 导入 / 对话框）
│   ├── outline-mode-picker.tsx # 大纲模式选择
│   ├── outline-scale-bar.tsx   # 大纲规模选择
│   └── ...
│
├── Library/              # 📚 素材库（/library）
│   ├── index.tsx         # 三 Tab 容器
│   ├── LibraryList.tsx / LibraryDetail.tsx   # 作品
│   ├── NovelCard.tsx     # 作品卡（封面 / 统计 / 悬停操作 / 右键 / 键盘菜单入口）
│   ├── NovelContextMenu.tsx / NovelDialogs.tsx  # 作品右键菜单 / 重命名+删除对话框
│   ├── novel-sort.ts     # 排序与上移下移的纯逻辑（可测）
│   ├── InspirationList.tsx / InspirationDetail.tsx / InspirationCard.tsx  # 灵感
│   ├── ScannerConfig.tsx # 本地扫描导入
│   └── CreateNovelDialog.tsx
│
└── Settings/             # ⚙️ 设置（/settings）
    ├── index.tsx
    ├── llm-section.tsx       # LLM 与密钥（14.1 KB）
    ├── data-section.tsx      # 数据与备份
    ├── ai-section.tsx        # AI 增强
    └── appearance-section.tsx# 外观
```

> 页面文件 ≤ 500 行；右栏每个 Tab 独立成文件。

### 2.2 API 客户端 `src/api/`

| 模块 | 职责 |
|---|---|
| `backend.ts` | **后端地址解析 + 就绪握手** —— 全项目唯一知道后端在哪的地方 |
| `streams.ts` | **NDJSON 流读取** + `detectStreamFailure()`（transport / server 两类失败） |
| `desktop.ts` | Tauri `invoke` 封装（`get_backend_url` / `backend_ready` / `get_backend_error`） |
| `novels.ts` `chapters.ts` `characters.ts` `outlines.ts` `inspirations.ts` | CRUD 端点 |
| `llm.ts` | provider 健康、模型列表、key 设置 |
| `skills.ts` `wordbanks.ts` `scanner.ts` `backup.ts` `settings.ts` `versions.ts` | 各功能域 |

**流消费方铁律**：所有 `readNdjsonStream` 的消费方，第一件事就是调 `detectStreamFailure(ev)`。
只判 `event === "error"` 的后果：HTTP 422/500 时 generator 正常 `return`，没有任何分支命中 → 界面永远转圈。

### 2.3 状态 `src/stores/`

| Store | 职责 |
|---|---|
| `workspace-store.ts` | **当前作品（全局唯一）**，持久化到 localStorage |
| `novels-store.ts` | 作品列表 CRUD |
| `novelStore.ts` | 当前作品详情 |
| `newbook-store.ts` | 开新书三步向导的跨步状态 |
| `settings-store.ts` | LLM / 密钥 / 主题配置 |
| `appearance-store.ts` | 外观偏好（主题 / 纸面跟随） |
| `uiStore.ts` | 通用 UI 状态（面板展开等） |

> **铁律**：当前作品是全局唯一状态 → 禁止在任何页面再放第二个「作品下拉」。
> 历史上重复了 3 处，切页面就丢。

### 2.4 工具层 `src/lib/`

纯函数 + 类型，无 React 依赖，全部有单测：

| 文件 | 用途 |
|---|---|
| `auto-scroll.ts` | 流式输出自动滚到底部 |
| `consistency.ts` | 人物一致性校验 |
| `novel-name.ts` | 作品重名规则（与后端 `novel_service.name_taken()` 必须一致） |
| `outline-merge.ts` | 大纲片段合并 |
| `outline-scale.ts` | 大纲规模档位 |
| `prose-insert.ts` | **流式追加正文**（插进最后一个段落内部 + 把 `\n` 变成真段落） |
| `prose-text.ts` | **正文字数口径**（非空白字符数，与后端 `count_prose_words` 一致） |
| `request-guard.ts` | 请求竞态防护（旧响应丢弃） |
| `types.ts` `utils.ts` | 类型与工具函数 |

### 2.5 自证脚本 `apps/desktop/scripts/`

Node 脚本，直接 import 生产实现，**不需要浏览器 / jsdom**：

| 文件 | 用途 |
|---|---|
| `verify-append.mjs` | 流式追加自证：旧逻辑复现 bug、新逻辑产出正确段落、重写不吞正文 |
| `repro-append.mjs` | 单独复现旧 bug 的形态（10 批次 → 10 个假段落） |

```bash
cd apps/desktop && node scripts/verify-append.mjs
```

---

## 3. 后端 `server/`

### 3.1 路由层 `src/api/`（16 个模块）

```
api/
├── main.py               # 应用装配 + 路由注册
├── novels.py             # 作品
├── chapters.py           # 章节 CRUD
├── chapter_generation.py # 章节流式生成 / 重写
├── chapter_versioning.py # 版本树 / 回滚 / diff
├── characters.py         # 人物卡
├── outlines.py           # 大纲
├── inspirations.py       # 灵感
├── llm.py                # provider 健康 / 模型列表 / key
├── settings.py           # 设置
├── skills.py             # Skill 执行
├── wordbanks.py          # 词库管理
├── scanner.py            # 本地扫描
├── export.py             # 导出（md / html / docx）
├── backup.py             # 备份 / 恢复
└── _stream_helpers.py    # ★ NDJSON 流式响应公共封装
```

> **铁律**：路由只做依赖注入 + 错误映射，不写业务逻辑。
> `_stream_helpers.py` 统一产出流内错误帧 `{"event": "error", "message": "..."}`。

### 3.2 业务层 `src/services/`（26 个模块）

| 域 | 模块 |
|---|---|
| 作品 / 章节 | `novel_service` `chapter_service` `chapter_generator` `chapter_rewriter` |
| 人物 | `character_service` `character_generator` `character_stream` `_character_helpers` |
| 大纲 | `outline_service` `outline_generator` `outline_skeleton` `outline_two_phase` `outline_single_phase` `outline_continuation` `outline_detail` `outline_prompts` `outline_errors` |
| 剧情 | `plot_service` |
| 灵感 / 词库 | `inspiration_service` `wordbank_service` `wordbank_importer` `wordbank_writer` |
| 导出 / 备份 | `export_service` `export_docx` `backup_service` |
| 设置 | `settings_service` |

**并行写库铁律**：`AsyncSession` 不是并发安全的 —— 两个协程同时 `flush()` 会抛
`Session is already flushing`。**并行的是 LLM 调用，串行的是写库**
（`asyncio.gather` 取结果 + for 循环串行入库，流式路径用 `asyncio.Lock`）。

### 3.3 基础设施 `src/core/`

```
core/
├── llm/                        # LLM 抽象（约 200 行 Protocol，不引任何 SDK）
│   ├── base.py                 # BaseLLMClient Protocol + ChatMessage / ChatResponse
│   ├── factory.py              # create_llm_client_for_scene() + provider 健康检查
│   ├── openai_compat.py        # httpx 手写，支持 mimo / minimax / OpenAI / 任意兼容端点
│   ├── ollama.py               # 本地 Ollama（/v1 协议）
│   ├── streaming.py            # ★ ThinkSplitter（拆分 <think> 思考流）
│   ├── thinking.py             # 推理模型思考内容抽取（reasoning_content 等三种字段名）
│   ├── cache.py                # 健康探测缓存（TTL + stale-while-revalidate）
│   ├── model_checker.py        # context_window / max_tokens 校验
│   ├── partial_json.py         # 半截 JSON 容错解析
│   └── formatting.py
│
├── skills/                     # Skill 系统
│   ├── base.py registry.py manager.py loader.py
│   └── builtin/                # 12 个内置技能
│       ├── word_counter.py           sensitive_word.py       chapter_summarizer.py
│       ├── character_extractor.py    consistency_checker.py genre_classifier.py
│       ├── outline_structurer.py     pacing_visualizer.py   plot_analyzer.py
│       ├── style_analyzer.py         read_local_file.py     web_search.py
│
├── security/                   # 密钥与加密
│   ├── dpapi.py                # Windows DPAPI（ctypes 调 crypt32.dll，零第三方依赖）
│   ├── secret_store.py         # 密钥链：环境变量 > DPAPI 文件 > 系统 Keyring
│   ├── encryption.py           # 内容加密（默认关闭）
│   └── keyring_manager.py
│
├── scanner/                    # novel_scanner / novel_detector / novel_importer
├── versioning/                 # version_tree.py / diff.py
│
├── chapter_context.py          # ★ 章节上下文组装（选人物卡 → 拼 prompt）
├── prose_format.py             # ★ 正文排版器（兜底断段 / 去汉字间空格 / 连续对白拆段 / 真实字数）
├── queue_merge.py              # ★ 多版本流合并（内容实时 + 里程碑保序）
├── paths.py                    # ★ 路径解析统一入口（开发态 / 打包态）
├── watchdog.py                 # 父进程看门狗（桌面端崩了后端自己退）
├── outline_scale.py            # 大纲规模档位
├── user_settings.py            # 用户级设置读写
├── config.py                   # 配置加载
└── logging.py                  # loguru setup_logging()
```

### 3.4 数据层

```
models/     # SQLAlchemy 2 ORM
├── novel.py      Novel
├── chapter.py    Chapter + ChapterVersion
├── character.py  Character + CharacterVersion
├── outline.py    Outline
├── inspiration.py Inspiration
└── base.py       Base / TimestampMixin

schemas/    # Pydantic 契约（API 输入输出）
db.py       # async engine + 外键 pragma + schema 自愈
```

**外键级联语义**（SQLite 默认不开外键，`db.py` 里显式 `PRAGMA foreign_keys=ON`）：

| 外键 | ondelete | 语义 |
|---|---|---|
| `chapters.novel_id` / `characters.novel_id` / `outlines.novel_id` | CASCADE | 删作品 → 连带删子行 |
| `chapter_versions.chapter_id` / `character_versions.character_id` | CASCADE | 删章节 / 人物 → 连带删版本 |
| `*_versions.parent_version_id` / `*.current_version_id` | SET NULL | 断链但保留数据 |
| `inspirations.novel_id` | SET NULL | **素材保留**，只脱离作品 |

**启动时的 schema 自愈**（`init_db()`，任何一步失败都不阻断启动）：

1. `Base.metadata.create_all` —— 建缺失的表（**只建表，不删表**）
2. `_ensure_missing_columns` —— 从 ORM 元数据推导，ALTER 补缺失列
3. `_purge_orphan_rows` —— 清「父行已删」的孤儿行

---

## 4. 配置 `config/`

```
config/
├── llm.yaml              # provider 定义 + 场景路由 + model_specs（max_tokens 等）
├── app.yaml              # 用户级默认配置
├── settings.example.yaml
├── prompts/              # 8 个提示词 YAML（章节生成/重写、人物卡、剧情、
│   │                     #   大纲三件套）
├── genres/               # 题材常识：xiuxian / dushi / xuanyi / yanqing
├── wordbanks/            # 题材词库（按板块分文件：修仙的词不会出现在都市板块）
├── skills/               # 用户自定义 Skill
└── skill_template/       # Skill 脚手架
```

> **venv 在仓库根，不在 `server/`** —— 根 `pyproject.toml` 是 uv workspace
> （`[tool.uv.workspace] members = ["server"]`），`uv sync` 在**根目录**执行，
> venv 落在 `<仓库根>/.venv/`。`scripts\dev.ps1` 和 `build_standalone.ps1` 都硬编码
> `<仓库根>\.venv\Scripts\python.exe`，所以这个位置不能改。

**提示词铁律**：所有 prompt 必须在 `config/prompts/*.yaml`，带 `version` + `changelog`。
**绝对不要**把 prompt 散落在 Python 代码里。

**场景路由**：业务代码不感知 provider，工厂按 `llm.yaml` 的 `routing` 自动解析：

```yaml
routing:
  chapter_generation: mimo
  chapter_rewrite: mimo
  summarize: ollama
```

---

## 5. 数据流

### 5.1 章节生成（典型场景）

```
写作页 → 点「生成正文」
  ↓ POST /chapters/{id}/generate
ChapterGenerator.stream_generate_parts()
  ↓ 加载 chapter / novel / characters
  ↓ get_chapter_outline()  取本章大纲
  ↓ select_relevant_characters()  只带「本章出场」人物卡
  ↓ 拼 prompt（config/prompts/chapter_generation.yaml）
  ↓ create_llm_client_for_scene("chapter_generation")
  ↓ ProseFormatter.feed(delta)   ★ 增量排版（见 §5.4）
  ↓ AsyncIterator[(kind, text)]   kind ∈ {thinking, text}
  ↓
StreamingResponse(ndjson)  ── HTTP chunked ──→ 前端直连 Python，不经过 Rust
  ↓
readNdjsonStream → classifyChapterStreamEvent
  ↓ for await 消费
  ├─ text     → prose-insert.ts 插进**最后一个段落内部**（不是文末新建段落）
  └─ thinking → 「模型思考中…」面板（净身后的纯中文）
  ↓
完成 → PATCH /chapters/{id}/content (trigger=llm_generate)
  ↓ ★ 取「编辑器全文」落库，不能用流式累积量
  │   （生成是追加、重写是替换选区，累积量都不是完整正文）
  ↓
DB: chapter.current_version_id = 新版本
```

### 5.2 多版本并行流（开新书的剧情 / 人物卡）

```
N 个版本并行调 LLM（asyncio.gather）
  ↓ 每个版本一个 queue
merge_queue_events_milestone_ordered()
  ↓
内容事件（thinking / delta）→ 实时透传，各卡各显示各的
里程碑事件（version_done / error）→ 按下标保序
  ↓
单条 NDJSON 流下发
```

> ⚠️ **不要用严格保序**（`merge_queue_events_ordered`）—— 那是「队列 1 消费完才消费队列 2」，
> 后面版本的内容全憋在队列里，等前一个彻底结束才同一毫秒涌出。
> 用户原话反馈："像是先生成但不输出，阻塞到一整个生成完毕才一口气很快地流式输出"。
> **"一口气"的直接成因就是这个**，不是模型慢，也不是前端缓冲。
>
> ⚠️ 失败版本也要参与保序 —— 失败的版本发 `error` 事件，**不会**发 `version_done`。
> 保序指针只认 `version_done` 的话，版本 1 失败时指针卡住，版本 2/3 的完成事件被压到整条流结束才吐。

### 5.3 启动握手

```
双击 Book Soul.exe
  ↓ Rust：分配随机空闲端口（不死绑 8765，避免多开冲突）
  ↓ Rust：定位 sidecar（exe 同级优先，Tauri 会剥掉 target-triple 后缀）
  ↓ Rust：拉起 book-soul-server.exe（传 --parent-pid）
  ↓ Rust：等后端 /ping 就绪 → 下发端口（get_backend_url）
  ↓ 前端：waitBackendReady() 后才拉数据，避免首屏 503
  ↓ 后端：watchdog 监控父进程，桌面端崩了后端自己退
```

### 5.4 正文排版链路（2026-10-30 新增）

> **背景**：用户实测「生成的小说文本多出大量空余字符，没有分段分行，
> 不同人物的对话无法区分」。取证：`len(content)=5338`，其中 **2024 个字符是换行**
> （1012 组 `\n\n`），真实正文只有 **3314 字**。

两个叠加的病因：

1. **前端把流式批次当成段落** —— 在文档**末尾** `insertText`，
   ProseMirror 会**新建一个段落**。每 16ms 一个 flush = 一个新段落，
   Tiptap 的 `getText()` 又用 `"\n\n"` 拼块 → 满篇假换行。
2. **模型可能不输出段落** —— 纯文本喂给 Tiptap 会被当成 HTML 解析成一个大段落。

现在的链路：

```
LLM 原始 delta
  ↓
【后端】core/prose_format.py :: ProseFormatter（增量）
  ├─ 汉字之间的空格删掉（英文单词之间的保留）
  ├─ 模型给的 \n → 段落分隔
  ├─ 兜底断段：段落 ≥30 字遇句末标点（。！？…）就断
  ├─ 段落 >120 字允许在弱断点（，、；：）断
  └─ 连续对白强制断段（“甲？”“乙。”→ 两段）
  ↓ 已排版的 NDJSON 流
【前端】lib/prose-insert.ts（纯 model/state，不碰 DOM）
  ├─ 插入位置 = **最后一个段落内部**（不是文末新建段落）
  └─ "\n\n" → 真段落边界
  ↓
Tiptap 编辑器（正文是纯文本，不是 HTML）
  ↓
【字数】prose-text.ts::countProseWords（非空白字符数）
       ←→ 后端 count_prose_words（口径必须一致）
```

> ⚠️ **字数口径 = 非空白字符数**（含中文标点，不含空格 / 换行）。
> 与 Word 的「字数」、网文平台（起点 / 番茄）一致。
> **禁止用 `len(content)`** —— 会把换行符全算进去，界面字数虚高。
>
> ⚠️ 前端 `countProseWords` 必须与后端 `count_prose_words` **完全一致**
> （注意 JS 的 `\s` **不匹配全角空格 U+3000**，要单独覆盖）。

**修复历史数据**：

```powershell
# 修复被假段落破坏的历史章节
python scripts\repair_chapter_paragraphs.py
# 只拆连续对白、保留原有段落划分
python scripts\repair_chapter_paragraphs.py --split-dialogue
```

### 5.5 作品名唯一 + 手动排序（2026-10-30 新增）

```
【前端】lib/novel-name.ts   预校验（给用户即时反馈）
【后端】services/novel_service.py  ← 权威（拦得住并发）
  ├─ name_taken(name, exclude_id)   撞名查询
  ├─ unique_name(base)              程序命名场景：base → base 2 → base 3
  └─ create / update 撞名 → NovelNameConflictError → API 409
  ↓
DB: novels.sort_order（手动顺序，下标越小越靠前）
  ↓
【前端】pages/Library/novel-sort.ts
  ★ 在可见列表里找邻居 → 在全量列表里交换两者的位置
    （只把可见子集发给后端的话，隐藏的作品会被排到队尾）
```

> **规则**：用户主动命名撞车 → 409 报错；程序自动命名 / 批量导入撞车 → 自动加序号。
> 同一时间只能有一本同名作品 —— 出现两本「修仙新作」时用户根本分不清哪本是自己刚写的。

---

## 6. 修改指引

| 我想改… | 去动这里 |
|---|---|
| 某个提示词 | `config/prompts/*.yaml`（**不要**改 Python 里的字符串） |
| 换一个 LLM provider | `config/llm.yaml`（**不要**改业务代码） |
| 章节生成逻辑 | `server/src/services/chapter_generator.py` + `core/chapter_context.py` |
| **正文排版规则**（断段 / 去空格 / 对白拆段） | `server/src/core/prose_format.py`（后端权威） |
| **正文插入位置**（插到段落内部 vs 文末） | `apps/desktop/src/lib/prose-insert.ts` |
| **字数口径** | 后端 `core/prose_format.py::count_prose_words` + 前端 `lib/prose-text.ts`（**两边必须一致**） |
| 大纲生成逻辑 | `server/src/services/outline_*.py`（骨架 / 两阶段 / 单阶段 / 补全分工明确） |
| 人物卡生成 | `server/src/services/character_generator.py` / `character_stream.py` |
| **作品命名规则** | 后端 `services/novel_service.py`（权威）+ 前端 `lib/novel-name.ts`（预校验） |
| **素材库作品排序** | `apps/desktop/src/pages/Library/novel-sort.ts`（纯函数，可单测） |
| 流式合并行为 | `server/src/core/queue_merge.py` |
| 桌面壳行为（端口 / 数据目录 / 拉起） | `apps/desktop/src-tauri/src/sidecar.rs` |
| 窗口 / 打包配置 | `apps/desktop/src-tauri/tauri.conf.json` |
| 写作页某个右栏 Tab | `apps/desktop/src/pages/Writing/tabs/<name>-tab.tsx` |
| 开新书某一步 | `apps/desktop/src/pages/NewBook/<step>-step.tsx` |
| 素材库作品卡 / 右键菜单 | `apps/desktop/src/pages/Library/NovelCard.tsx` / `NovelContextMenu.tsx` / `NovelDialogs.tsx` |
| 流事件解析 | `apps/desktop/src/api/streams.ts`（**所有**流消费方共用） |
| 数据表结构 | `server/src/models/` + `server/src/schemas/`（**两边都要改**，见下方警告） |

> ⚠️ **ORM 列 ↔ Pydantic schema ↔ 前端 payload，三方必须对齐。**
> - Pydantic `extra="ignore"` 会**静默吞字段** —— ORM 有列、prompt 让 LLM 生成、service 也取了值，
>   但 schema 少这一项 → 从头到尾没存进库，UI 永远空，**没有任何报错**。
> - Pydantic `extra="forbid"` + 前端多发字段 = **必现 422**。
>
> 排查"前端能填、后端存不进去"这类问题，先做三方对账，不要从 UI 层猜。

---

## 7. 构建产物与体积

```
apps/desktop/src-tauri/
├── target/                        # Rust 编译缓存（8.7 GB！gitignore）
│   ├── debug/                     # 6.8 GB —— 可随时删，重建几分钟
│   └── release/                   # 1.9 GB —— 删了要重编 20-40 分钟
│       └── bundle/nsis/*.exe      # 安装包（32.4 MB）
├── binaries/                      # sidecar exe（31 MB，build_sidecar.ps1 生成）
└── ...

server/
├── build/                         # PyInstaller 中间目录（48 MB，可删）
└── dist/                          # PyInstaller 产物（31 MB）

dist/Book Soul/                    # ★ 独立版成品（36 MB）—— 整个文件夹拷走就能用
```

**体积说明**：成品只有 36 MB，工作区能到 9.6 GB，全是 Rust / PyInstaller / pnpm 的构建缓存。
清缓存前先确认 `dist\Book Soul\` 和 `data\` 里的东西还在。

**防复发**：`CARGO_TARGET_DIR` 指到项目外，Rust 的构建产物根本不落在项目目录里。

---

## 8. 测试分布

| 层 | 位置 | 数量 |
|---|---|---|
| 后端 | `server/tests/`（58 个文件） | **781** |
| 前端 | `apps/desktop/src/**/__tests__/`（22 个文件） | **275** |
| 合计 | | **1056** |

**流式契约测试是强制的**：所有流式端点必须有「第一个 chunk 在数据源结束前就被 yield」的断言，
用假 SSE 源（带间隔的 async generator）实现。没有这条测试，假流式 bug 一定会复发。

关键契约测试文件：

| 文件 | 锁住什么 |
|---|---|
| `test_llm_streaming_contract.py` | 必须用 `client.stream()`，不能用 `client.post()` |
| `test_think_splitter.py` | 思考内容不能被丢弃 |
| `test_queue_merge.py` / `test_queue_merge_milestone.py` | 内容实时 + 里程碑保序 + 失败版本不阻塞 |
| `test_character_generator.py` | 并行生成时全部人物卡都要入库 |
| `test_llm_cache.py` | 预检与 `/llm/health` 只探测一次 |
| `test_foreign_keys.py` | SQLite 外键约束真的生效 |
| `test_prose_format.py` | 兜底断段 / 去汉字间空格 / 连续对白拆段 / 真实字数 |
| `test_novel_manage.py` | 作品名唯一（409）/ 自动加序号 / 手动排序 |

前端侧（`apps/desktop/src/**/__tests__/`）：

| 文件 | 锁住什么 |
|---|---|
| `lib/__tests__/prose-insert.test.ts` | 插入到**最后一个段落内部**，不新建假段落 |
| `lib/__tests__/prose-text.test.ts` | 字数口径与后端一致（含全角空格 U+3000） |
| `lib/__tests__/novel-name.test.ts` | 作品名规则（前后端一致） |
| `pages/Library/__tests__/novel-sort.test.ts` | 上移 / 下移同时改对「可见顺序」和「全量顺序」 |

> 前端自证脚本（不依赖浏览器）：`cd apps/desktop && node scripts/verify-append.mjs`
> —— 直接 import **生产实现**，不是复刻一份。之前复刻版测出的行为与线上代码不一致，
> 差点造成误判。

---

## 9. 文档体系

```
docs/
├── DESIGN.md            # 界面设计规范 —— 信息架构 + 视觉令牌（改 UI 前必读）
├── PROJECT_STRUCTURE.md # 本文件
├── START_GUIDE.md       # 三种启动方式 + 人工验证清单
├── USER_GUIDE.md        # 各页面功能使用
├── TROUBLESHOOTING.md   # 排障 + 应急处理
├── ARCHITECTURE.md      # 分层 / 数据模型 / LLM 抽象 / 流式协议 / 关键决策
├── API.md               # 后端端点参考
├── SKILLS.md            # 12 个内置 Skill + 自定义写法
└── screenshots/         # 真机截图（5 张，真实数据）
```

根目录的三份：

| 文件 | 定位 |
|---|---|
| `AGENTS.md` | **技术规范**（强制）—— 技术栈 / 分层铁律 / LLM 调用规范 / 打包 / 测试 / 提交流程 |
| `DEVELOPMENT_CONSTRAINTS.md` | **行为约束** —— 沟通 / 流程 / 决策 / agent 工作流 |
| `PROJECT_PLAN.md` | **历史快照 + 决策记录** —— 核心设计决策、明确不做的事、54 个模块的完成状态 |
| `SECURITY.md` | 安全策略 —— 密钥存储 / 数据流向 / 备份路径 |

**分三层，别混**：

| 层 | 回答什么问题 | 谁维护 |
|---|---|---|
| 现状层（`docs/` 除 PROJECT_PLAN 外） | **现在**是什么样 | 跟代码同步改 |
| 决策层（`PROJECT_PLAN.md` §1） | **为什么**这么设计、不做什么 | 很少变 |
| 约束层（`AGENTS.md` / `DEVELOPMENT_CONSTRAINTS.md`） | **必须**怎么做 | 改了要用户确认 |

> **现状层必须随代码同步**，否则会出现「文档比代码更落后」——
> 2026-10 的 UI 重设计把一级导航从 6 项砍到 4 项，README 和 USER_GUIDE
> 却整整几周都在描述已经不存在的页面，用户照着点根本找不到。
> `AGENTS.md` §2.2 有这条硬要求。

