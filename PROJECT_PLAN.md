# Book Soul · 项目开发完整计划书

> 文档版本 v1.1 · 2026-09-02
> 项目代号：Book Soul
> 工作目录：`C:\Users\JZ\Desktop\Book Soul`
>
> **配套文档**：
> - [USER_CHECKLIST.md](./USER_CHECKLIST.md) - 用户人工要做的事（环境、Key、验证）
> - [AGENTS.md](./AGENTS.md) - 项目规范（强制）
> - [README.md](./README.md) - 项目说明
> - [SECURITY.md](./SECURITY.md) - 安全策略
> 目标用户：JEE（网文作者 + 自学开发者，vibe coding 模式）
> 部署目标：Tauri 桌面应用 + GitHub 公开仓库

---

## Summary

本计划为 JEE（初次接触开发、采用 vibe coding 模式）量身定制的完整开发计划，**将生成两份独立文档**：

1. **PROJECT_PLAN.md**（项目开发计划书，agent 使用）—— 详尽到每个 Phase、每个模块、每个步骤、每个文件、每个验证点。新对话窗口中的 agent 可直接照此实施。
2. **USER_CHECKLIST.md**（用户准备清单，用户使用）—— 用户人工需要做的所有事情：装环境、申请 Key、素材准备、对话模板、检验方法。

**核心设计决策**（不再变动）：
- 桌面壳：Tauri 2
- 前端：React 18 + TypeScript + Vite + Tailwind + shadcn/ui + Tiptap
- 后端：Python 3.11+ + FastAPI + SQLAlchemy 2 + SQLite
- 向量库：ChromaDB（嵌入式）
- LLM 抽象：自研 ~200 行 Protocol（不用 LangChain）
- 包管理：uv（Python）+ pnpm（Node）
- 核心特色：人物卡驱动一致性 + Skill/Tool 系统 + 双模式 LLM（云端 + 本地 Ollama）
- 部署：纯本地，无账号系统；数据存用户可指定目录；扫描本地文件夹接入
- 质量保障：pre-commit（ruff + gitleaks）+ GitHub Actions（CI）+ 提交拦截机制
- 发布：GitHub 公开仓库，.env 完全隔离

**JEE 指定的开发期决策**（v1.1 新增，JEE 已确认）：
- **题材优先级**：修仙 → 都市 → 悬疑 → 言情（从左到右依次递减）
- **辅助开发模型上下文**：1M tokens（minimax-M3）
- **用户自定义模型警告**：当用户配置的模型不支持 1k-8k 每章生成数时，UI 弹警告提醒（实现见模块 0.5）
- **题材优先级**：修仙 → 都市 → 悬疑 → 言情（从左到右依次递减）
- **辅助开发模型上下文**：1M tokens（minimax-M3）
- **用户自定义模型警告**：当用户配置的模型不支持 1k-8k 每章生成数时，UI 弹警告提醒

**关键非目标**（明确不做）：
- ❌ 用户账号系统
- ❌ 主密码/密码派生
- ❌ 云端同步
- ❌ 多人协作
- ❌ LangChain 重型框架
- ❌ Electron

**目标周期**：8-10 周（按 1-2 小时/天 vibe coding 节奏）

---

## ⚠️ 重要声明：开发期间可自由修改

**这份计划不是一成不变的。** 在开发过程中，你可以随时要求修改：

1. **改技术栈**：发现某个库不好用，可以换
2. **改功能范围**：发现某个功能不需要，可以删
3. **改优先级**：发现某个 Phase 应该先做，可以调
4. **改实现方式**：发现某个模块的方案不对，可以重做
5. **加新功能**：开发中有新想法，可以加

**修改流程**：
- 在新对话中直接说"修改计划书第 X 章"或"把 Phase Y 改成 Z"
- agent 会更新本计划文件 + 工作目录的 PROJECT_PLAN.md
- **不需要重做已完成的工作**，除非你明确说"重做"

**修改建议**：
- 每完成 2-3 个模块后做一次"回顾"
- 哪些模块实际比预想简单/复杂？调整后续估算
- 用户体验是否如预期？调整后续功能设计

---

## 📖 5 分钟导读（让你快速看懂）

> 如果你没时间看完整份计划，先看这一节。

### 一句话总结

**这是一个本地优先的小说 AI 写作桌面应用，分 8 个阶段开发，每个阶段拆成可独立验证的模块。**

### 你需要做的 3 件事

1. **装环境**（一次性 1-2 天）：Python、Node、Rust、Git、VS Code、uv、pnpm
2. **每次开新对话**：用模板跟 agent 说"做 Phase X 模块 Y"
3. **验证功能**：每个模块完成后，agent 给你"用户验证清单"，你按清单在 UI 测

### agent 每次会做的 5 件事

1. 读取 PROJECT_PLAN.md 中对应部分
2. 写 100-300 行代码
3. 写测试（pytest）
4. 跑 ruff + pytest + pre-commit
5. 给你"用户验证清单"和"commit 消息"

### 8 个阶段是什么（极简版）

| Phase | 内容 | 周期 |
|-------|------|------|
| 0 | 环境 + 工具链 + Hello World | 3-5 天 |
| 1 | 5 个核心实体的后端 API + 人物卡 | 1-1.5 周 |
| 2 | 桌面壳 + 5 个页面 | 1 周 |
| 3 | 灵感园（开新书全流程） | 2 周 |
| 4 | 创作（章节生成 + 重写 + 版本） | 2.5 周 |
| 5 | 质量检测（6 维度评分） | 1.5 周 |
| 6 | 仓库（本地扫描接入） | 1 周 |
| 7 | 优化 + Skill 完善 | 1 周 |
| 8 | 打包发布 | 1 周 |

### 4 大功能模块（用户视角）

| 功能 | 用户能做什么 |
|------|-------------|
| **灵感园** | 选题材 → 抽灵感词 → 生成剧情 → 生成大纲 → 生成人物卡 → 保存 |
| **创作** | 选作品 → 流式生成章节 → 选段 AI 重写 → 版本对比 → 导出 |
| **质量检测** | 选章节 → 自动评分（文笔/逻辑/节奏/人设/题材）→ 看报告 |
| **仓库** | 看灵感库（含人物卡/大纲）→ 看藏书馆 → 扫描本地小说接入 |

### 关键技术名词速查

| 名词 | 是什么 | 比喻 |
|------|--------|------|
| Tauri | 桌面应用框架 | 餐厅外壳 |
| FastAPI | Python 后端 | 厨房 |
| React | 前端 UI | 大堂 |
| SQLite | 数据库 | 仓库的货架 |
| ChromaDB | 向量数据库 | 搜索引擎 |
| Tiptap | 富文本编辑器 | 笔记本 |
| LLM | AI 大脑 | 代笔作家 |
| Skill | LLM 工具 | 作家的小工具箱 |
| 人物卡 | 角色档案 | 演员的人设表 |
| pre-commit | 提交前检查 | 出厂质检 |
| GitHub Actions | 自动测试 | 24h 监控 |

---

# 文档 1：PROJECT_PLAN.md（agent 实施用）

> 退出 Plan Mode 后，此文档将写入 `C:\Users\JZ\Desktop\Book Soul\PROJECT_PLAN.md`

## 0. 文档使用说明

### 0.1 本文档结构

每个 Phase 包含：
- **目标**：本阶段要达成什么
- **模块列表**：本阶段拆分的可独立交付模块
- **每个模块**：
  - 目标
  - 涉及文件
  - 具体步骤（逐步骤、可执行）
  - 关键代码示例
  - 验证方法（用户可独立验证）
  - 检验清单（user 检验 + agent 自检）
- **阶段产出物**

### 0.2 agent 实施原则

1. **严格按模块顺序**：用户每次开新对话只说"继续 Phase X 模块 Y"，agent 按本文档执行
2. **单模块代码量控制**：单个模块产出代码不超过 300 行；超出则拆分
3. **每个模块完成后**：自动运行 ruff + pytest + pre-commit，确保通过
4. **代码必须含测试**：业务逻辑必须配 pytest 单元测试
5. **不允许幻觉库**：所有依赖必须真实存在于 PyPI/npm；agent 写代码前必须 Google 确认
6. **遵循 AGENTS.md**：项目根目录的 AGENTS.md 是强制规范

### 0.3 用户对话模板

用户每次开新对话，按以下模板：

```
我现在做 [项目名] 的 [Phase X 模块 Y]。

完整计划在项目根目录 PROJECT_PLAN.md，请读取。

本次任务：
- 目标：
- 涉及文件：
- 验收标准：

请按计划实施，并在完成后：
1. 运行 ruff format + ruff check + pytest
2. 给出本模块的验证步骤清单
3. 列出我需要在 UI 或功能上人工验证的点
```

---

## 1. 项目总览

### 1.1 核心功能模块

| 模块 | 简述 |
|------|------|
| **灵感园** | 开新书（题材→灵感词→剧情→大纲→人物卡）+ 续写 |
| **创作** | 章节生成 + 选区 AI 重写 + 版本控制 + 提示词框 |
| **质量检测** | 多维度评分（文笔/逻辑/节奏/人设/题材合规）+ 报告 |
| **仓库** | 灵感库（带人物卡/大纲查看）+ 藏书馆 + 本地扫描接入 |

### 1.2 横切关注点

| 系统 | 简述 |
|------|------|
| **人物卡体系** | 全局驱动创作一致性的核心子系统 |
| **Skill/Tool 系统** | 预装 + 用户自定义的 LLM 工具集 |
| **LLM 抽象层** | 多 provider 统一接口（minimax/OpenAI/Ollama） |
| **状态机** | 开新书、续写流程的状态追踪 |
| **记忆系统** | 项目级 + 会话级 + RAG 检索 |
| **版本控制** | 自研版本树，章节/人物卡/大纲通用 |
| **本地扫描** | 扫描用户指定文件夹，识别并接入小说 |
| **质量门禁** | 代码质量 + 隐私检测 + 提交拦截 |

---

## 2. 目录结构（最终态）

```
book-soul/
├── apps/
│   ├── desktop/                          # Tauri 桌面壳
│   │   ├── src-tauri/
│   │   │   ├── src/main.rs
│   │   │   ├── tauri.conf.json
│   │   │   └── Cargo.toml
│   │   └── package.json
│   └── web/                              # React 前端
│       ├── src/
│       │   ├── pages/
│       │   │   ├── Inspiration/          # 灵感园
│       │   │   ├── Creation/             # 创作
│       │   │   ├── QualityCheck/         # 质量检测
│       │   │   ├── Library/              # 仓库
│       │   │   ├── Skills/               # 技能市场
│       │   │   └── Settings/             # 设置
│       │   ├── components/               # 通用组件
│       │   ├── stores/                   # Zustand 状态
│       │   ├── api/                      # Tauri Cmd 封装
│       │   ├── lib/                      # 工具函数
│       │   ├── types/                    # TS 类型
│       │   ├── App.tsx
│       │   └── main.tsx
│       ├── index.html
│       ├── tailwind.config.js
│       ├── vite.config.ts
│       ├── tsconfig.json
│       └── package.json
├── server/                               # Python 后端
│   ├── src/
│   │   ├── api/
│   │   │   ├── novels.py
│   │   │   ├── chapters.py
│   │   │   ├── characters.py
│   │   │   ├── outlines.py
│   │   │   ├── inspirations.py
│   │   │   ├── library.py
│   │   │   ├── skills.py
│   │   │   ├── quality.py
│   │   │   ├── scanner.py
│   │   │   ├── settings.py
│   │   │   └── main.py
│   │   ├── core/
│   │   │   ├── config.py                 # 配置加载
│   │   │   ├── llm/
│   │   │   │   ├── base.py
│   │   │   │   ├── openai_compat.py
│   │   │   │   ├── ollama.py
│   │   │   │   ├── factory.py
│   │   │   │   └── streaming.py
│   │   │   ├── memory/
│   │   │   │   ├── project_memory.py
│   │   │   │   ├── rag_memory.py
│   │   │   │   └── conversation_memory.py
│   │   │   ├── workflow/
│   │   │   │   ├── state_machine.py
│   │   │   │   ├── new_book.py
│   │   │   │   └── continue_book.py
│   │   │   ├── versioning/
│   │   │   │   ├── version_tree.py
│   │   │   │   └── diff.py
│   │   │   ├── security/
│   │   │   │   ├── encryption.py
│   │   │   │   └── keyring_manager.py
│   │   │   ├── prompts/
│   │   │   │   └── loader.py
│   │   │   ├── skills/
│   │   │   │   ├── base.py
│   │   │   │   ├── registry.py
│   │   │   │   ├── loader.py
│   │   │   │   ├── executor.py
│   │   │   │   └── builtin/
│   │   │   │       ├── word_counter.py
│   │   │   │       ├── sensitive_word.py
│   │   │   │       ├── chapter_summarizer.py
│   │   │   │       ├── character_extractor.py
│   │   │   │       ├── plot_analyzer.py
│   │   │   │       ├── web_search.py
│   │   │   │       ├── read_local_file.py
│   │   │   │       ├── consistency_checker.py
│   │   │   │       ├── style_analyzer.py
│   │   │   │       ├── pacing_visualizer.py
│   │   │   │       ├── outline_structurer.py
│   │   │   │       └── genre_classifier.py
│   │   │   └── scanner/
│   │   │       ├── novel_detector.py
│   │   │       ├── novel_scanner.py
│   │   │       └── novel_importer.py
│   │   ├── models/                       # SQLAlchemy ORM
│   │   │   ├── base.py
│   │   │   ├── novel.py
│   │   │   ├── chapter.py
│   │   │   ├── character.py
│   │   │   ├── outline.py
│   │   │   ├── inspiration.py
│   │   │   └── version.py
│   │   ├── schemas/                      # Pydantic
│   │   │   ├── novel.py
│   │   │   ├── chapter.py
│   │   │   ├── character.py
│   │   │   ├── outline.py
│   │   │   ├── inspiration.py
│   │   │   └── skill.py
│   │   ├── services/                     # 业务逻辑
│   │   │   ├── novel_service.py
│   │   │   ├── chapter_service.py
│   │   │   ├── character_service.py
│   │   │   ├── outline_service.py
│   │   │   ├── inspiration_service.py
│   │   │   ├── library_service.py
│   │   │   ├── quality_service.py
│   │   │   ├── skill_service.py
│   │   │   └── scanner_service.py
│   │   └── db.py
│   ├── tests/
│   │   ├── test_config.py
│   │   ├── test_llm.py
│   │   ├── test_memory.py
│   │   ├── test_skills.py
│   │   ├── test_character_service.py
│   │   └── ...
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── README.md
├── config/
│   ├── llm.yaml
│   ├── genres/
│   │   ├── xuanhuan.yaml
│   │   ├── dushi.yaml
│   │   ├── kehuan.yaml
│   │   ├── xuanyi.yaml
│   │   └── yanqing.yaml
│   ├── wordbanks/
│   │   ├── xuanhuan.yaml
│   │   ├── dushi.yaml
│   │   └── ...
│   ├── styles/
│   ├── prompts/
│   │   ├── inspiration_keywords.yaml
│   │   ├── plot_generation.yaml
│   │   ├── outline_complete.yaml
│   │   ├── outline_freedom.yaml
│   │   ├── character_generation.yaml
│   │   ├── chapter_generation.yaml
│   │   ├── chapter_rewrite.yaml
│   │   ├── quality_writing.yaml
│   │   ├── quality_logic.yaml
│   │   ├── quality_pacing.yaml
│   │   ├── quality_consistency.yaml
│   │   ├── quality_genre.yaml
│   │   └── ...
│   └── skills/
│       ├── builtin/
│       │   └── *.yaml                    # 预装 skill 元数据
│       └── user/                         # 用户自定义 skill（运行时生成）
├── data/                                 # 运行时数据（不入 git）
│   ├── novels/
│   ├── chroma/
│   ├── logs/
│   └── book-soul.db
├── .github/
│   └── workflows/
│       ├── ci.yml                        # CI（lint + test + build）
│       └── release.yml                   # 自动发版
├── docs/
│   ├── USER_GUIDE.md
│   ├── API.md
│   └── ARCHITECTURE.md
├── scripts/
│   ├── setup.ps1                         # Windows 初始化脚本
│   ├── dev.ps1                           # 开发启动脚本
│   └── check.ps1                         # 检验脚本
├── .gitignore
├── .env.example
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── .ruff.toml
├── AGENTS.md                             # ⭐ 项目规范
├── LICENSE                               # MIT
├── PROJECT_PLAN.md                       # 本文档
├── USER_CHECKLIST.md                     # 用户准备清单
├── pyproject.toml                        # uv workspace 根
├── README.md
└── SECURITY.md
```

---

## 3. 关键技术决策表

| 决策 | 选择 | 理由 |
|------|------|------|
| 桌面框架 | Tauri 2 | 包小、性能好、Rust 可桥接 |
| 前端 | React 18 + TS + Vite | 主流生态 |
| 状态管理 | Zustand | 轻量、TS 友好 |
| UI 库 | shadcn/ui + Tailwind | 源码可控 |
| 编辑器 | Tiptap | 选区操作原生支持 |
| 后端 | FastAPI | 异步原生、自动文档 |
| LLM 抽象 | 自研 Protocol | 避开 LangChain 重型抽象 |
| 数据库 | SQLite | 零配置 |
| ORM | SQLAlchemy 2 | 主流、类型安全 |
| 向量库 | ChromaDB | 嵌入式、免服务 |
| Python 包管理 | uv | 快速 |
| Node 包管理 | pnpm | 高效 |
| 加密 | Fernet（可选） | 简化模式 |
| API Key 存储 | 系统 Keyring | OS 凭据 |
| 数据目录 | 用户可配置 | 默认 `~/Documents/BookSoul/` |
| Lint | ruff | 快、合并 isort+flake8+black |
| 类型检查 | mypy | 严格度可调 |
| 测试 | pytest | 标准 |
| Pre-commit | pre-commit + ruff + gitleaks | 质量门禁 |
| CI | GitHub Actions | 公开仓库友好 |

---

## 4. 数据库 Schema（最终态）

```sql
-- 作品
CREATE TABLE novels (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  genre TEXT NOT NULL,
  style TEXT,
  description TEXT,
  status TEXT DEFAULT 'draft',
  outline_mode TEXT,                     -- 'complete' / 'freedom'
  file_path TEXT,                        -- 本地文件路径
  imported INTEGER DEFAULT 0,            -- 是否扫描接入
  read_only INTEGER DEFAULT 0,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- 人物卡
CREATE TABLE characters (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL,                    -- 主角/主角团/反派/正派/队友/其他
  basic_info TEXT,
  personality TEXT,
  habits TEXT,
  thinking TEXT,
  relationships TEXT,
  growth_arc TEXT,
  current_version_id INTEGER,
  is_active INTEGER DEFAULT 1,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  FOREIGN KEY (novel_id) REFERENCES novels(id)
);

-- 人物卡版本
CREATE TABLE character_versions (
  id INTEGER PRIMARY KEY,
  character_id INTEGER NOT NULL,
  parent_version_id INTEGER,
  snapshot JSON NOT NULL,
  change_reason TEXT,
  trigger_event TEXT,
  created_at TIMESTAMP,
  FOREIGN KEY (character_id) REFERENCES characters(id)
);

-- 大纲
CREATE TABLE outlines (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL,
  outline_type TEXT NOT NULL,
  structure JSON NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- 章节
CREATE TABLE chapters (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER NOT NULL,
  chapter_number INTEGER NOT NULL,
  title TEXT,
  outline TEXT,
  current_version_id INTEGER,
  word_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'outline',
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- 章节版本
CREATE TABLE chapter_versions (
  id INTEGER PRIMARY KEY,
  chapter_id INTEGER NOT NULL,
  parent_version_id INTEGER,
  content TEXT NOT NULL,
  diff TEXT,
  trigger TEXT,
  prompt TEXT,
  metadata JSON,
  created_at TIMESTAMP
);

-- 灵感
CREATE TABLE inspirations (
  id INTEGER PRIMARY KEY,
  novel_id INTEGER,
  type TEXT NOT NULL,
  content JSON NOT NULL,
  source TEXT,
  tags TEXT,
  created_at TIMESTAMP
);

-- Skill 注册
CREATE TABLE skills (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  source TEXT,                          -- 'builtin' / 'user'
  enabled INTEGER DEFAULT 1,
  config JSON,
  created_at TIMESTAMP
);

-- Skill 调用日志
CREATE TABLE skill_calls (
  id INTEGER PRIMARY KEY,
  skill_name TEXT NOT NULL,
  novel_id INTEGER,
  input JSON,
  output JSON,
  duration_ms INTEGER,
  created_at TIMESTAMP
);

-- 用户配置
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value JSON,
  updated_at TIMESTAMP
);

-- 通用版本表（兼容大纲、人物卡、章节）
CREATE TABLE versions (
  id INTEGER PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  parent_version_id INTEGER,
  content TEXT NOT NULL,
  diff TEXT,
  trigger TEXT,
  prompt TEXT,
  metadata JSON,
  created_at TIMESTAMP,
  INDEX idx_entity (entity_type, entity_id)
);
```

---

## 5. 分阶段开发详细步骤

> 每个 Phase 内含多个模块，每个模块可独立开发、检验、提交。

---

### Phase 0：环境与基建（3-5 天）

**目标**：项目骨架可运行，能通过 hello world 验证 LLM 调用、Tauri 启动、GitHub Actions。

#### 模块 0.1：创建 GitHub 仓库（用户操作）

- **文件**：无（GitHub 网页操作）
- **步骤**：
  1. GitHub 创建空仓库 `book-soul`，**不勾选** Initialize with README
  2. 本地克隆：`git clone https://github.com/JEE/book-soul.git`
- **验证**：仓库存在，可 push
- **用户人工**：是

#### 模块 0.2：基础配置文件

- **文件**：
  - `.gitignore`
  - `.env.example`
  - `.gitleaks.toml`
  - `LICENSE` (MIT)
  - `README.md`（初版占位）
  - `SECURITY.md`
  - `AGENTS.md` ⭐
- **步骤**：
  1. agent 提供每个文件完整内容
  2. 用户复制到本地
- **AGENTS.md 关键内容**：
  ```markdown
  # AGENTS.md

  ## 项目概述
  Book Soul - 小说 AI 写作桌面应用

  ## 技术栈
  - 后端：Python 3.11+ / FastAPI / SQLAlchemy 2 / SQLite / ChromaDB
  - 前端：React 18 / TypeScript / Vite / Tiptap / Tailwind / shadcn/ui
  - 桌面：Tauri 2
  - LLM：自研抽象层（不用 LangChain）
  - 包管理：uv (Python) / pnpm (Node)

  ## 目录约定
  - 业务代码在 `server/src/`
  - 配置文件在 `config/`
  - 测试在 `server/tests/`
  - 不在 `server/src/` 直接写文件操作，统一走 services

  ## 命名规范
  - 文件名：snake_case (Python) / kebab-case (前端)
  - 类名：PascalCase
  - 函数名：snake_case
  - 常量：UPPER_SNAKE_CASE
  - React 组件：PascalCase

  ## 严格禁止
  - ❌ 不用 LangChain
  - ❌ 不用 Flask
  - ❌ 不用 Electron
  - ❌ 前端代码不硬编码任何 API Key
  - ❌ .env 不提交 git
  - ❌ 不用 print 调试（用 loguru）
  - ❌ 单一函数不超 200 行
  - ❌ SQL 不用参数化（必须用 ORM）

  ## 提示词管理
  - 所有 prompt 在 `config/prompts/*.yaml`
  - 必带 version 字段
  - 改动更新 changelog

  ## 安全规范
  - 所有 SQL 用 ORM（参数化）
  - 所有文件操作检查路径（防越界）
  - 所有网络请求加超时
  - 所有用户输入校验
  - API Key 存系统 Keyring，不入配置文件
  ```
- **验证**：所有文件存在并被 git 跟踪（.env 不被跟踪）
- **用户人工**：复制内容

#### 模块 0.3：Python 后端初始化

- **文件**：
  - `pyproject.toml`（根 + server）
  - `server/src/__init__.py`
  - `server/src/main.py`（FastAPI 入口）
  - `server/src/api/main.py`（路由注册）
  - `server/src/core/config.py`
  - `server/src/db.py`
- **步骤**：
  1. 创建 `pyproject.toml`（uv workspace 模式）
  2. 创建 `server/pyproject.toml`（声明依赖）
  3. 创建 FastAPI 最小应用（含 `/ping` 接口）
  4. 配置加载器（用 pydantic-settings）
- **关键代码 `server/pyproject.toml`**：
  ```toml
  [project]
  name = "book-soul-server"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
    "aiosqlite>=0.20",
    "alembic>=1.14",
    "loguru>=0.7",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "tenacity>=9.0",
  ]

  [project.optional-dependencies]
  dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.7",
    "mypy>=1.13",
    "pre-commit>=4.0",
  ]

  [tool.ruff]
  line-length = 100
  target-version = "py311"

  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "T"]
  ignore = ["E501"]

  [tool.pytest.ini_options]
  asyncio_mode = "auto"
  testpaths = ["tests"]
  ```
- **关键代码 `server/src/main.py`**：
  ```python
  from fastapi import FastAPI
  from contextlib import asynccontextmanager
  from loguru import logger
  from .api import router as api_router
  from .core.config import settings
  from .db import init_db

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      logger.info("Starting Book Soul server")
      await init_db()
      yield
      logger.info("Shutting down")

  app = FastAPI(title="Book Soul", lifespan=lifespan)
  app.include_router(api_router)

  if __name__ == "__main__":
      import uvicorn
      uvicorn.run("src.main:app", host="127.0.0.1", port=8765, reload=True)
  ```
- **验证**：
  ```bash
  cd server
  uv sync
  uv run python -m src.main
  # 访问 http://127.0.0.1:8765/docs 看到 Swagger UI
  curl http://127.0.0.1:8765/ping
  # 返回 {"status": "ok"}
  ```
- **用户人工**：在终端跑验证命令，截图反馈
- **检验清单**：
  - [ ] `/docs` 页面能打开
  - [ ] `/ping` 返回 200
  - [ ] 没有 import error

#### 模块 0.4：日志与配置

- **文件**：
  - `server/src/core/config.py`
  - `server/src/core/logging.py`
  - `config/llm.yaml`（初版）
  - `config/app.yaml`（用户配置）
- **关键代码 `config.py`**：
  ```python
  from pathlib import Path
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      model_config = SettingsConfigDict(
          env_file=".env",
          env_file_encoding="utf-8",
          extra="ignore",
      )

      # 数据目录
      data_dir: Path = Path.home() / "Documents" / "BookSoul"

      # 服务
      host: str = "127.0.0.1"
      port: int = 8765

      # 日志
      log_level: str = "INFO"

      # 加密（可选）
      encryption_enabled: bool = False

  settings = Settings()
  ```
- **验证**：写测试 `test_config.py` 验证配置加载
- **用户人工**：跑测试，确认通过

#### 模块 0.5：LLM 抽象层

- **文件**：
  - `server/src/core/llm/base.py`
  - `server/src/core/llm/openai_compat.py`
  - `server/src/core/llm/ollama.py`
  - `server/src/core/llm/factory.py`
  - `server/src/core/llm/streaming.py`
  - `config/llm.yaml`
  - `server/tests/test_llm.py`
- **关键代码 `base.py`**：
  ```python
  from typing import Protocol, AsyncIterator
  from dataclasses import dataclass

  @dataclass
  class ChatMessage:
      role: str
      content: str

  @dataclass
  class ChatResponse:
      content: str
      usage: dict

  class BaseLLMClient(Protocol):
      async def chat(
          self,
          messages: list[ChatMessage],
          *,
          model: str | None = None,
          temperature: float = 0.7,
          max_tokens: int | None = None,
          stream: bool = False,
      ) -> ChatResponse | AsyncIterator[str]: ...

      def count_tokens(self, text: str) -> int: ...
  ```
- **关键代码 `factory.py`**：
  ```python
  from pathlib import Path
  import yaml
  from .base import BaseLLMClient
  from .openai_compat import OpenAICompatClient
  from .ollama import OllamaClient

  _config_cache: dict | None = None

  def load_llm_config() -> dict:
      global _config_cache
      if _config_cache is None:
          config_path = Path("config/llm.yaml")
          with open(config_path, encoding="utf-8") as f:
              _config_cache = yaml.safe_load(f)
      return _config_cache

  def create_llm_client(provider: str) -> BaseLLMClient:
      config = load_llm_config()
      provider_config = config["providers"][provider]
      match provider_config["type"]:
          case "openai_compat":
              return OpenAICompatClient(provider_config)
          case "ollama":
              return OllamaClient(provider_config)
          case _:
              raise ValueError(f"Unknown provider: {provider_config['type']}")
  ```
- **关键代码 `llm.yaml`（含模型规格 + 上下文窗口）**：
  ```yaml
  providers:
    minimax:
      type: openai_compat
      base_url: ${MINIMAX_BASE_URL}
      api_key: ${MINIMAX_API_KEY}
      models: [MiniMax-M3]
      default_model: MiniMax-M3
      model_specs:
        MiniMax-M3:
          context_window: 1000000       # 1M tokens
          max_output_tokens: 64000
          supports_chapter_range: true
          quality_tier: premium

    openai:
      type: openai_compat
      base_url: https://api.openai.com/v1
      api_key: ${OPENAI_API_KEY}
      models: [gpt-4o-mini, gpt-4o]
      model_specs:
        gpt-4o-mini:
          context_window: 128000
          max_output_tokens: 16384
          quality_tier: standard
        gpt-4o:
          context_window: 128000
          max_output_tokens: 4096
          quality_tier: premium

    ollama:
      type: ollama
      base_url: http://localhost:11434/v1
      api_key: ollama
      models: [qwen2.5:7b, llama3.1:8b]
      model_specs:
        qwen2.5:7b:
          context_window: 32768
          max_output_tokens: 8192
          quality_tier: local
        llama3.1:8b:
          context_window: 128000
          max_output_tokens: 8192
          quality_tier: local

  chapter_limits:
    min_chars: 1000                   # JEE 决策：下限 1k
    max_chars: 8000                   # JEE 决策：上限 8k

  routing:
    inspiration: minimax
    chapter_generation: minimax
    quality_check: ollama
    summarize: ollama
    rewrite: minimax
  ```

- **关键代码 `model_checker.py`（新文件，模型能力校验）**：
  ```python
  # server/src/core/llm/model_checker.py
  from dataclasses import dataclass
  from .factory import load_llm_config

  @dataclass
  class ModelWarning:
      level: str  # 'error' | 'warning' | 'info'
      message: str

  @dataclass
  class ModelCheckResult:
      provider: str
      model: str
      context_window: int
      max_output_tokens: int
      warnings: list[ModelWarning]
      can_generate_chapter: bool

  def check_model_capability(
      provider: str,
      model: str,
      chapter_limits: tuple[int, int] = (1000, 8000),
  ) -> ModelCheckResult:
      """检查模型是否支持 1k-8k 字章节生成

      规则：
      - context_window 必须 ≥ 32k（容纳 prompt + 历史 + 8k 字输出）
      - max_output_tokens 必须 ≥ 章节上限的 2x
      """
      config = load_llm_config()
      provider_cfg = config['providers'][provider]
      model_spec = provider_cfg.get('model_specs', {}).get(model, {})

      warnings: list[ModelWarning] = []
      context_window = model_spec.get('context_window', 0)
      max_output = model_spec.get('max_output_tokens', 0)

      min_chars, max_chars = chapter_limits
      max_chars_tokens = max_chars * 2      # 中文 1 字 ≈ 1.5-2 tokens
      min_context_needed = 32_000

      if context_window < min_context_needed:
          warnings.append(ModelWarning(
              level='error',
              message=f"模型 {model} 上下文仅 {context_window} tokens，无法支持 1k-8k 字生成"
          ))

      if max_output < max_chars_tokens:
          warnings.append(ModelWarning(
              level='warning',
              message=f"模型 {model} 最大输出 {max_output} tokens，8k 字章节可能需分多次"
          ))

      can_generate = (
          context_window >= min_context_needed
          and max_output >= max_chars_tokens // 2
      )

      return ModelCheckResult(
          provider=provider, model=model,
          context_window=context_window,
          max_output_tokens=max_output,
          warnings=warnings,
          can_generate_chapter=can_generate,
      )
  ```

- **前端警告机制**（设置页 + 创作页触发）：
  ```typescript
  // apps/desktop/src/components/ModelWarning.tsx
  export function ModelWarningBanner({ result }: { result: ModelCheckResult }) {
    if (result.warnings.length === 0) return null;
    const errors = result.warnings.filter(w => w.level === 'error');
    const warns = result.warnings.filter(w => w.level === 'warning');
    return (
      <div className="space-y-2">
        {errors.map((w, i) => (
          <div key={i} className="p-3 bg-red-50 border border-red-200 rounded">
            <p className="font-semibold text-red-800">无法生成章节</p>
            <p className="text-sm text-red-700">{w.message}</p>
            <p className="text-xs text-red-600 mt-1">建议：换 ≥ 32k 上下文的模型</p>
          </div>
        ))}
        {warns.map((w, i) => (
          <div key={i} className="p-3 bg-yellow-50 border border-yellow-200 rounded">
            <p className="font-semibold text-yellow-800">章节生成可能受限</p>
            <p className="text-sm text-yellow-700">{w.message}</p>
          </div>
        ))}
      </div>
    );
  }
  ```

- **触发点**：
  1. **设置页**：用户切换 LLM 时立即检测
  2. **创作页**：点击"生成章节"前检测
  3. **error 级别**：阻塞"生成"按钮（用户必须确认或换模型）
  4. **warning 级别**：允许继续但弹确认对话框

- **验证**：
  - 写测试 `test_model_checker.py`，覆盖各种 model 规格
  - 真机测试：故意配一个 context_window=4k 的假模型，验证 UI 弹红框
  - 真机测试：配 qwen2.5:7b（32k 上下文），验证弹黄框
  - 真机测试：配 minimax-M3（1M 上下文），验证不弹警告

- **用户人工**：
  - 切换 LLM 时观察警告
  - 验证 error 级别确实阻塞"生成"按钮
  - 验证 warning 级别允许继续但提示

#### 模块 0.6：数据库初始化

- **文件**：
  - `server/src/db.py`
  - `server/src/models/base.py`
  - `server/alembic.ini`
  - `server/alembic/env.py`
  - `server/alembic/versions/0001_initial.py`
- **关键代码 `db.py`**：
  ```python
  from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
  from sqlalchemy.orm import DeclarativeBase
  from .core.config import settings

  class Base(DeclarativeBase):
      pass

  engine = create_async_engine(
      f"sqlite+aiosqlite:///{settings.data_dir}/book-soul.db",
      echo=False,
  )

  async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

  async def init_db():
      async with engine.begin() as conn:
          await conn.run_sync(Base.metadata.create_all)
  ```
- **关键代码 `models/novel.py`（示例）**：
  ```python
  from datetime import datetime
  from sqlalchemy import String, Integer, DateTime
  from sqlalchemy.orm import Mapped, mapped_column
  from .base import Base

  class Novel(Base):
      __tablename__ = "novels"

      id: Mapped[int] = mapped_column(Integer, primary_key=True)
      name: Mapped[str] = mapped_column(String(200), nullable=False)
      genre: Mapped[str] = mapped_column(String(50), nullable=False)
      # ... 完整字段见 schema 章节
  ```
- **验证**：
  - 启动应用，DB 文件被创建
  - alembic upgrade head 不报错
- **用户人工**：检查 `data/book-soul.db` 文件存在

#### 模块 0.7：Tauri 桌面壳

- **文件**：
  - `apps/desktop/src-tauri/Cargo.toml`
  - `apps/desktop/src-tauri/tauri.conf.json`
  - `apps/desktop/src-tauri/src/main.rs`
  - `apps/desktop/package.json`
  - `apps/desktop/src/index.html`
  - `apps/desktop/src/main.tsx`（React 入口）
  - `apps/desktop/src/App.tsx`
- **步骤**：
  1. `pnpm create tauri-app` 选择 React + TS
  2. 改 `tauri.conf.json` 配置窗口
  3. 写最小 React 应用
- **关键代码 `tauri.conf.json`**：
  ```json
  {
    "productName": "Book Soul",
    "version": "0.1.0",
    "identifier": "com.booksoul.app",
    "build": {
      "beforeDevCommand": "pnpm dev",
      "devUrl": "http://localhost:5173",
      "beforeBuildCommand": "pnpm build"
    },
    "app": {
      "windows": [{ "title": "Book Soul", "width": 1400, "height": 900 }]
    }
  }
  ```
- **关键代码 `main.rs`**：
  ```rust
  use tauri::Manager;

  #[tauri::command]
  async fn ping() -> String {
      "pong".to_string()
  }

  fn main() {
      tauri::Builder::default()
          .invoke_handler(tauri::generate_handler![ping])
          .run(tauri::generate_context!())
          .expect("error while running tauri application");
  }
  ```
- **验证**：
  - `pnpm tauri dev` 启动桌面应用
  - 窗口打开显示 "Hello Book Soul"
- **用户人工**：运行命令，确认窗口出现

#### 模块 0.8：质量门禁（pre-commit + ruff）

- **文件**：
  - `.ruff.toml`（如未在 pyproject）
  - `.pre-commit-config.yaml`
  - `server/tests/test_*.py`（每模块配测试）
- **关键代码 `.pre-commit-config.yaml`**：
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.7.4
      hooks:
        - id: ruff
          args: [--fix]
        - id: ruff-format

    - repo: https://github.com/gitleaks/gitleaks
      rev: v8.18.0
      hooks:
        - id: gitleaks

    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v5.0.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-json
  ```
- **验证**：
  - `pre-commit install` 安装钩子
  - 故意写错代码，`git commit` 应失败
  - 故意写含 `sk-xxx` 的字符串，应被 gitleaks 拦截
- **用户人工**：跑故意错误 commit，验证拦截生效

#### 模块 0.9：GitHub Actions CI

- **文件**：
  - `.github/workflows/ci.yml`
  - `.github/workflows/release.yml`
- **关键代码 `ci.yml`**：
  ```yaml
  name: CI

  on:
    push:
      branches: [main]
    pull_request:
      branches: [main]

  jobs:
    backend:
      runs-on: windows-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with:
            python-version: '3.11'
        - run: pip install uv
        - run: cd server && uv sync --all-extras
        - run: cd server && uv run ruff check .
        - run: cd server && uv run ruff format --check .
        - run: cd server && uv run pytest --cov
        - run: cd server && uv run mypy src

    frontend:
      runs-on: windows-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with:
            node-version: '20'
        - run: npm install -g pnpm
        - run: cd apps/desktop && pnpm install
        - run: cd apps/desktop && pnpm tsc --noEmit
        - run: cd apps/desktop && pnpm build
  ```
- **验证**：push 到 GitHub，CI 跑通（绿色✓）
- **用户人工**：检查 GitHub Actions 页面

#### 模块 0.10：Hello World 端到端验证

- **步骤**：
  1. Tauri 启动 → 显示窗口
  2. 窗口有按钮 "测试 LLM"
  3. 点击按钮 → 通过 Tauri Cmd 调 Python → Python 调 LLM → 返回结果 → 显示在窗口
- **文件**：
  - `apps/desktop/src/App.tsx`（含按钮）
  - `apps/desktop/src/api/llm.ts`（封装 Tauri Cmd）
- **关键代码 `App.tsx`**：
  ```tsx
  import { invoke } from "@tauri-apps/api/core";
  import { useState } from "react";

  function App() {
    const [response, setResponse] = useState("");
    const [loading, setLoading] = useState(false);

    async function testLLM() {
      setLoading(true);
      try {
        const result = await invoke("test_llm", { prompt: "用一句话介绍《凡人修仙传》" });
        setResponse(result as string);
      } catch (e) {
        setResponse(`错误：${e}`);
      } finally {
        setLoading(false);
      }
    }

    return (
      <div className="p-8">
        <h1 className="text-2xl font-bold">Book Soul</h1>
        <button
          onClick={testLLM}
          disabled={loading}
          className="mt-4 px-4 py-2 bg-blue-500 text-white rounded"
        >
          {loading ? "调用中..." : "测试 LLM"}
        </button>
        {response && <p className="mt-4">{response}</p>}
      </div>
    );
  }

  export default App;
  ```
- **验证**：点击按钮看到 LLM 真实回复
- **用户人工**：是（必须看到 LLM 回复）

#### 阶段 0 产出物

- [ ] GitHub 仓库可访问
- [ ] 本地 `pnpm tauri dev` 启动应用
- [ ] 点击按钮能调通 LLM
- [ ] CI 在 GitHub 上跑通
- [ ] pre-commit 拦截测试通过
- [ ] `.env` 不在 git 中

---

### Phase 1：核心后端服务（1-1.5 周）

> 用户的核心需求：作品、章节、人物卡、大纲、灵感库的 CRUD。**人物卡是重点**。

#### 模块 1.1：作品 CRUD

- **文件**：
  - `server/src/models/novel.py`
  - `server/src/schemas/novel.py`
  - `server/src/services/novel_service.py`
  - `server/src/api/novels.py`
  - `server/tests/test_novel_service.py`
- **关键代码 `novel_service.py`**：
  ```python
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import select
  from ..models.novel import Novel
  from ..schemas.novel import NovelCreate, NovelUpdate

  class NovelService:
      def __init__(self, session: AsyncSession):
          self.session = session

      async def create(self, data: NovelCreate) -> Novel:
          novel = Novel(**data.model_dump())
          self.session.add(novel)
          await self.session.commit()
          await self.session.refresh(novel)
          return novel

      async def list_all(self) -> list[Novel]:
          result = await self.session.execute(select(Novel))
          return list(result.scalars())

      async def get(self, novel_id: int) -> Novel | None:
          return await self.session.get(Novel, novel_id)

      async def update(self, novel_id: int, data: NovelUpdate) -> Novel:
          novel = await self.get(novel_id)
          if not novel:
              raise ValueError(f"Novel {novel_id} not found")
          for k, v in data.model_dump(exclude_unset=True).items():
              setattr(novel, k, v)
          await self.session.commit()
          return novel

      async def delete(self, novel_id: int) -> None:
          novel = await self.get(novel_id)
          if novel:
              await self.session.delete(novel)
              await self.session.commit()
  ```
- **测试**：`test_novel_service.py` 覆盖 create/list/get/update/delete
- **验证**：
  - pytest 全过
  - `/docs` 能看到 novels 接口
  - 用 curl 测试一遍 CRUD
- **用户人工**：跑 `pytest`，跑 curl

#### 模块 1.2：人物卡 CRUD ⭐ 重点

- **文件**：
  - `server/src/models/character.py`
  - `server/src/schemas/character.py`
  - `server/src/services/character_service.py`
  - `server/src/api/characters.py`
  - `server/tests/test_character_service.py`
- **额外功能**：
  - 性格变化记录（growth_arc 自动追加）
  - 人物卡版本化
- **关键代码 `character_service.py`（核心方法）**：
  ```python
  from datetime import datetime
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import select
  from ..models.character import Character, CharacterVersion
  from ..schemas.character import (
      CharacterCreate, CharacterUpdate, CharacterGrowthUpdate
  )

  class CharacterService:
      def __init__(self, session: AsyncSession):
          self.session = session

      async def create(self, data: CharacterCreate) -> Character:
          """创建人物卡 + 初始版本"""
          character = Character(**data.model_dump(exclude={"initial_data"}))
          self.session.add(character)
          await self.session.flush()

          # 创建初始版本
          version = CharacterVersion(
              character_id=character.id,
              parent_version_id=None,
              snapshot=data.model_dump(),
              change_reason="initial",
          )
          self.session.add(version)
          await self.session.flush()

          character.current_version_id = version.id
          await self.session.commit()
          return character

      async def get_active_characters(self, novel_id: int) -> list[Character]:
          """获取作品所有活跃人物（创作时使用）"""
          result = await self.session.execute(
              select(Character)
              .where(Character.novel_id == novel_id, Character.is_active == 1)
          )
          return list(result.scalars())

      async def update_growth(
          self,
          character_id: int,
          event: str,
          new_personality: str,
      ) -> CharacterVersion:
          """记录性格变化

          触发方式：主角经历某事件后性格改变
          自动追加到 growth_arc
          """
          character = await self.session.get(Character, character_id)
          if not character:
              raise ValueError(f"Character {character_id} not found")

          # 追加到 growth_arc
          growth_entry = f"[{datetime.now().strftime('%Y-%m-%d')}] {event}：性格 → {new_personality}"
          character.growth_arc = (character.growth_arc or "") + "\n" + growth_entry
          character.personality = new_personality

          # 创建新版本
          new_version = CharacterVersion(
              character_id=character.id,
              parent_version_id=character.current_version_id,
              snapshot={
                  "personality": new_personality,
                  "growth_arc": character.growth_arc,
                  "trigger_event": event,
              },
              change_reason="event_trigger",
              trigger_event=event,
          )
          self.session.add(new_version)
          await self.session.flush()

          character.current_version_id = new_version.id
          await self.session.commit()
          return new_version

      async def list_versions(self, character_id: int) -> list[CharacterVersion]:
          """查看人物卡版本历史"""
          result = await self.session.execute(
              select(CharacterVersion)
              .where(CharacterVersion.character_id == character_id)
              .order_by(CharacterVersion.created_at.desc())
          )
          return list(result.scalars())
  ```
- **测试**：
  - 创建人物卡
  - 性格变化记录
  - 版本历史查询
- **验证**：pytest + curl 测试性格变化 API
- **用户人工**：用 curl 测一遍

#### 模块 1.3：章节 CRUD + 版本基础

- **文件**：
  - `server/src/models/chapter.py`
  - `server/src/schemas/chapter.py`
  - `server/src/services/chapter_service.py`
  - `server/src/api/chapters.py`
  - `server/tests/test_chapter_service.py`
- **功能**：
  - 章节 CRUD
  - 创建版本（暂不实现 diff 和复杂回滚）
  - 字数统计
- **关键代码（章节创建 + 版本）**：
  ```python
  async def create(self, data: ChapterCreate) -> Chapter:
      chapter = Chapter(
          novel_id=data.novel_id,
          chapter_number=data.chapter_number,
          title=data.title,
          outline=data.outline,
          word_count=len(data.content) if data.content else 0,
      )
      self.session.add(chapter)
      await self.session.flush()

      if data.content:
          version = ChapterVersion(
              chapter_id=chapter.id,
              parent_version_id=None,
              content=data.content,
              trigger="user_create",
              word_count=chapter.word_count,
          )
          self.session.add(version)
          await self.session.flush()
          chapter.current_version_id = version.id

      await self.session.commit()
      return chapter
  ```

#### 模块 1.4：大纲 CRUD

- **文件**：同 1.3 模式
- **数据结构**：JSON 字段存分卷/章节树
- **重点**：支持完整版 + 创作型两种 mode

#### 模块 1.5：灵感库 CRUD

- **文件**：同 1.3 模式
- **content JSON 字段**：按 type 存不同结构

#### 模块 1.6：加密服务（简化版）

- **文件**：
  - `server/src/core/security/encryption.py`
  - `server/src/core/security/keyring_manager.py`
  - `server/tests/test_encryption.py`
- **设计**：
  ```python
  # encryption.py
  from cryptography.fernet import Fernet
  from .keyring_manager import KeyManager

  class EncryptionService:
      def __init__(self):
          self.key = KeyManager.get_or_create_key()
          self.cipher = Fernet(self.key) if self.key else None

      def encrypt(self, plaintext: str) -> str | None:
          if not self.cipher:
              return plaintext
          return self.cipher.encrypt(plaintext.encode()).decode()

      def decrypt(self, ciphertext: str | None) -> str | None:
          if not self.cipher or not ciphertext:
              return ciphertext
          return self.cipher.decrypt(ciphertext.encode()).decode()

  # keyring_manager.py
  import keyring
  import os

  class KeyManager:
      SERVICE = "BookSoul"

      @staticmethod
      def get_or_create_key() -> bytes:
          key_str = keyring.get_password(KeyManager.SERVICE, "encryption_key")
          if key_str:
              return key_str.encode()

          key = Fernet.generate_key()
          keyring.set_password(KeyManager.SERVICE, "encryption_key", key.decode())
          return key
  ```
- **重要**：加密默认关闭，配置项 `encryption_enabled: bool = False`

#### 模块 1.7：记忆系统骨架

- **文件**：
  - `server/src/core/memory/project_memory.py`
  - `server/src/core/memory/rag_memory.py`
  - `server/src/core/memory/conversation_memory.py`
- **本期只实现接口和空实现**，Phase 4 完善

#### 阶段 1 产出物

- [ ] 5 个核心实体的 CRUD 完整
- [ ] 人物卡版本化、性格变化 API 可用
- [ ] 加密服务可开关
- [ ] pytest 覆盖率 > 70%
- [ ] ruff / mypy 通过
- [ ] API 文档可访问

---

### Phase 2：桌面壳 + 前端骨架（1 周）

#### 模块 2.1：路由与基础布局

- **文件**：
  - `apps/desktop/src/App.tsx`（React Router）
  - `apps/desktop/src/components/Layout.tsx`（侧边栏 + 主区）
  - `apps/desktop/src/pages/*/index.tsx`（5 个页面占位）
- **关键代码 `App.tsx`**：
  ```tsx
  import { HashRouter, Routes, Route } from "react-router-dom";
  import Layout from "./components/Layout";
  import Inspiration from "./pages/Inspiration";
  import Creation from "./pages/Creation";
  import QualityCheck from "./pages/QualityCheck";
  import Library from "./pages/Library";
  import Settings from "./pages/Settings";

  export default function App() {
    return (
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Inspiration />} />
            <Route path="/creation" element={<Creation />} />
            <Route path="/quality" element={<QualityCheck />} />
            <Route path="/library" element={<Library />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </HashRouter>
    );
  }
  ```

#### 模块 2.2：shadcn/ui 集成

- **步骤**：`pnpm dlx shadcn@latest init` + 按需 `add` 组件
- **用户必须装**：`button`, `input`, `card`, `dialog`, `tabs`, `select`, `textarea`, `toast`, `dropdown-menu`

#### 模块 2.3：Tauri ↔ Python 通信

- **文件**：
  - `apps/desktop/src/api/index.ts`（统一封装）
  - `apps/desktop/src/api/novels.ts`
  - `apps/desktop/src/api/characters.ts`
  - ...
- **关键代码 `api/index.ts`**：
  ```typescript
  import { invoke } from "@tauri-apps/api/core";

  export async function callApi<T>(command: string, args?: Record<string, unknown>): Promise<T> {
    try {
      return await invoke<T>(command, args);
    } catch (error) {
      console.error(`API ${command} failed:`, error);
      throw error;
    }
  }
  ```
- **后端对应**：每个 Python 接口用 `#[tauri::command]` 暴露
  ```python
  from fastapi import FastAPI
  from .api import router
  app = FastAPI()
  app.include_router(router)

  # Tauri 调用通过 HTTP 访问 FastAPI
  # 不需要单独的 Tauri 命令包装（除非有特殊需求）
  ```
- **Tauri 配置**：开放 HTTP 请求到 127.0.0.1:8765
  ```json
  // tauri.conf.json
  "allowlist": {
    "http": {
      "all": false,
      "request": ["http://127.0.0.1:8765/*"]
    }
  }
  ```
- **用户人工**：跑应用，看到 5 个菜单

#### 模块 2.4：设置页基础

- **文件**：
  - `apps/desktop/src/pages/Settings/index.tsx`
  - 后端：`server/src/api/settings.py` + `server/src/services/settings_service.py`
- **功能**：
  - LLM Provider 选择
  - API Key 录入（存 Keyring）
  - 数据目录设置
  - 主题切换
  - 加密开关

#### 模块 2.5：Zustand 状态管理

- **文件**：
  - `apps/desktop/src/stores/novelStore.ts`
  - `apps/desktop/src/stores/uiStore.ts`
  - `apps/desktop/src/stores/settingsStore.ts`

#### 阶段 2 产出物

- [ ] 桌面应用 5 页面可访问
- [ ] 设置页可改 LLM Provider
- [ ] API Key 存 Keyring
- [ ] 主题切换正常
- [ ] 数据目录可设置

---

### Phase 3：灵感园 - 开新书（2 周）

#### 模块 3.1：题材选择 + 词库系统

- **JEE 决策的题材优先级**（v1.1 更新）：
  | 优先级 | 题材 | 文件名 | 备注 |
  |--------|------|--------|------|
  | P0（必做）| 修仙 | `xiuxian.yaml` | 网文大头，词库 800+ |
  | P1（必做）| 都市 | `dushi.yaml` | 词库 500+ |
  | P2（必做）| 悬疑 | `xuanyi.yaml` | 词库 500+ |
  | P3（必做）| 言情 | `yanqing.yaml` | 词库 500+ |

- **文件**：
  - `config/genres/xiuxian.yaml` ⭐ P0
  - `config/genres/dushi.yaml` ⭐ P1
  - `config/genres/xuanyi.yaml` ⭐ P2
  - `config/genres/yanqing.yaml` ⭐ P3
  - `config/wordbanks/xiuxian.yaml`
  - `config/wordbanks/dushi.yaml`
  - `config/wordbanks/xuanyi.yaml`
  - `config/wordbanks/yanqing.yaml`
  - `server/src/services/wordbank_service.py`
  - `apps/desktop/src/pages/Inspiration/GenreSelect.tsx`

- **词库 YAML 结构**（以修仙 P0 为例）：
  ```yaml
  name: 修仙
  themes: [修炼, 突破, 灵气, 丹药, 法宝, 飞升, 心魔, 渡劫, ...]
  characters: [主角, 师父, 反派, 道侣, 师妹, 长老, ...]
  plots: [退婚, 打脸, 夺宝, 复仇, 升级, 秘境, 宗门大比, ...]
  scenes: [宗门, 拍卖会, 战斗, 遗迹, 秘境, 洞府, ...]
  items: [飞剑, 玉佩, 灵草, 秘籍, 灵兽, 储物袋, ...]
  ```

- **题材顺序配置**（前端用，控制选择顺序）：
  ```typescript
  // apps/desktop/src/config/genres.ts
  export const GENRE_PRIORITY = [
    { id: 'xiuxian', name: '修仙', tier: 'P0', emoji: '🗡️' },
    { id: 'dushi', name: '都市', tier: 'P1', emoji: '🏙️' },
    { id: 'xuanyi', name: '悬疑', tier: 'P2', emoji: '🔍' },
    { id: 'yanqing', name: '言情', tier: 'P3', emoji: '💕' },
  ] as const;
  ```
- **关键代码 `wordbank_service.py`**：
  ```python
  from pathlib import Path
  import yaml
  import random

  class WordbankService:
      def __init__(self, genre: str):
          self.genre = genre
          self._load()

      def _load(self):
          path = Path(f"config/wordbanks/{self.genre}.yaml")
          with open(path, encoding="utf-8") as f:
              self.data = yaml.safe_load(f)

      def get_random_words(self, category: str, n: int = 10) -> list[str]:
          words = self.data.get(category, [])
          return random.sample(words, min(n, len(words)))

      def get_all_categories(self) -> list[str]:
          return list(self.data.keys())
  ```
- **用户人工**：在 UI 选"修仙"（P0 优先级最高），看到灵感词

#### 模块 3.2：灵感词生成/刷新/锁定

- **文件**：
  - `apps/desktop/src/pages/Inspiration/KeywordBoard.tsx`
  - `server/src/api/inspirations.py`
- **功能**：
  - 刷新按钮（生成新词）
  - 锁定按钮（已选不参与刷新）
  - 多选 / 全选 / 反选
  - 手动添加输入框
  - 提示词框（始终显示）

#### 模块 3.3：简要剧情生成

- **文件**：
  - `config/prompts/plot_generation.yaml`
  - `server/src/services/inspiration_service.py`
  - `apps/desktop/src/pages/Inspiration/PlotGenerator.tsx`
- **关键代码**：
  ```python
  async def generate_plot(
      self,
      genre: str,
      keywords: list[str],
      n_versions: int = 3,
  ) -> list[str]:
      """批量生成简要剧情"""
      prompt_template = self.prompts["plot_generation"]
      results = []
      for _ in range(n_versions):
          prompt = prompt_template.format(
              genre=genre,
              keywords=", ".join(keywords),
          )
          response = await self.llm.chat([ChatMessage("user", prompt)])
          results.append(response.content)
      return results
  ```
- **用户人工**：选词 → 生成 3 个剧情 → 看到结果

#### 模块 3.4：完整版大纲生成

- **文件**：
  - `config/prompts/outline_complete.yaml`
  - `config/prompts/outline_freedom.yaml`
  - `server/src/services/outline_service.py`
- **关键代码**：
  ```python
  async def generate_complete_outline(
      self,
      novel_id: int,
      plot: str,
  ) -> dict:
      """生成完整版大纲（分卷 + 章节）"""
      # 加载 LLM 抽象
      # 构造 prompt（含题材常识）
      # 调用 LLM
      # 解析 JSON 输出
      # 存入数据库
  ```
- **输出结构**（LLM 需输出 JSON）：
  ```json
  {
    "volumes": [
      {
        "title": "第一卷 初入修仙",
        "summary": "...",
        "chapters": [
          {"title": "第一章 偶得传承", "summary": "..."},
          ...
        ]
      }
    ]
  }
  ```

#### 模块 3.5：人物卡自动生成 ⭐ 核心

- **文件**：
  - `config/prompts/character_generation.yaml`
  - `server/src/services/character_service.py`（扩展 `generate_from_outline`）
- **关键代码**：
  ```python
  async def generate_from_outline(
      self,
      novel_id: int,
      outline: dict,
  ) -> list[Character]:
      """从大纲提取并生成人物卡"""
      # Step 1: 提取人物列表
      extract_prompt = f"""
      从以下大纲中提取所有人物，按角色分类：
      主角 / 主角团 / 反派 / 正派 / 队友 / 其他

      大纲：{json.dumps(outline, ensure_ascii=False)}

      输出 JSON 列表：[{{"name": "...", "role": "..."}}]
      """
      characters_data = await self.llm.chat(...)
      characters_data = json.loads(characters_data.content)

      # Step 2: 为每个人物生成完整卡
      characters = []
      for char in characters_data:
          gen_prompt = f"""
          为以下人物生成完整卡：
          姓名：{char['name']}
          角色：{char['role']}
          题材：修仙
          大纲上下文：{...}

          输出 YAML 格式：
          ```yaml
          basic_info: ...
          personality: ...
          habits: ...
          thinking: ...
          relationships: ...
          growth_arc: ...
          ```
          """
          char_card_yaml = await self.llm.chat(...)
          # 解析 + 入库
          ...
          characters.append(character)

      return characters
  ```
- **用户人工**：在 UI 看自动生成的人物卡，可接受/编辑/重生

#### 模块 3.6：人物卡管理 UI

- **文件**：
  - `apps/desktop/src/pages/Inspiration/CharacterManager.tsx`
  - `apps/desktop/src/components/CharacterCard.tsx`
- **功能**：
  - 显示所有人物（按角色分组）
  - 接受 / 编辑 / 重生成
  - 手动添加
  - 性格变化记录入口

#### 模块 3.7：状态机实现

- **文件**：
  - `server/src/core/workflow/state_machine.py`
  - `server/src/core/workflow/new_book.py`
- **关键代码**：
  ```python
  class NewBookStateMachine:
      STATES = [
          "idle", "select_genre", "generate_keywords", "select_keywords",
          "generate_plot", "edit_plot", "select_outline_mode",
          "generate_outline", "edit_outline", "generate_characters",
          "edit_characters", "save", "done"
      ]

      TRANSITIONS = {
          "idle": ["select_genre"],
          "select_genre": ["generate_keywords"],
          "generate_keywords": ["select_keywords"],
          "select_keywords": ["generate_plot"],
          # ...
      }

      def __init__(self, session_id: str):
          self.session_id = session_id
          self.current_state = "idle"
          self.context: dict = {}

      def transition(self, to: str, **context):
          if to not in self.TRANSITIONS.get(self.current_state, []):
              raise ValueError(f"Invalid transition: {self.current_state} -> {to}")
          self.current_state = to
          self.context.update(context)
  ```

#### 模块 3.8：保存到灵感库 + 导出 md

- **文件**：
  - `server/src/services/inspiration_service.py`（保存）
  - `apps/desktop/src/pages/Inspiration/SavePanel.tsx`
- **导出**：
  - 纯 Python `open()` 写 .md
  - 模板：作品名 + 题材 + 简介 + 人物卡 + 大纲

#### 阶段 3 产出物

- [ ] 可在 UI 完成"开新书"全流程
- [ ] 灵感词可刷新/锁定
- [ ] 剧情批量生成
- [ ] 大纲生成（两种 mode）
- [ ] 人物卡自动生成 + 人工调整
- [ ] 保存到灵感库
- [ ] 导出 md

---

### Phase 4：创作（2.5 周）

#### 模块 4.1：作品选择 + 章节列表

- **文件**：
  - `apps/desktop/src/pages/Creation/NovelSelector.tsx`
  - `apps/desktop/src/pages/Creation/ChapterList.tsx`

#### 模块 4.2：Tiptap 集成

- **步骤**：
  1. `pnpm dlx shadcn@latest add`（按需）
  2. 安装：`pnpm add @tiptap/react @tiptap/starter-kit @tiptap/extension-selection`
  3. 创建基础编辑器组件
- **关键代码**：
  ```tsx
  import { useEditor, EditorContent } from "@tiptap/react";
  import StarterKit from "@tiptap/starter-kit";

  export function NovelEditor({ content, onChange, onSelection }: Props) {
    const editor = useEditor({
      extensions: [StarterKit],
      content,
      onUpdate: ({ editor }) => onChange(editor.getHTML()),
      onSelectionUpdate: ({ editor }) => {
        const { from, to } = editor.state.selection;
        if (from !== to) onSelection({ from, to, text: editor.state.doc.textBetween(from, to) });
      },
    });

    return <EditorContent editor={editor} />;
  }
  ```

#### 模块 4.3：章节生成（流式）

- **文件**：
  - `config/prompts/chapter_generation.yaml`
  - `server/src/api/chapters.py`（流式接口）
  - `server/src/services/chapter_service.py`（生成逻辑）
- **关键代码（流式 + 人物卡注入）**：
  ```python
  async def generate_chapter_stream(
      self,
      novel_id: int,
      chapter_number: int,
      outline_mode: str,
  ) -> AsyncIterator[str]:
      # 1. 加载上下文
      novel = await self.novel_service.get(novel_id)
      characters = await self.character_service.get_active_characters(novel_id)
      outline = await self.outline_service.get(novel_id)
      chapter_outline = outline.get_chapter_outline(chapter_number)
      recent_summaries = await self.get_recent_summaries(novel_id, n=3)
      previous_tail = await self.get_chapter_tail(novel_id, chapter_number - 1, chars=1500)

      # 2. 拼 prompt
      prompt = self.prompts["chapter_generation"].format(
          novel_name=novel.name,
          genre=novel.genre,
          outline_mode=outline_mode,
          all_characters=format_characters(characters),
          novel_outline=outline.structure,
          chapter_outline=chapter_outline,
          recent_summaries=recent_summaries,
          previous_tail=previous_tail,
          target_word_count=4000,
      )

      # 3. 流式调用
      client = create_llm_client("minimax")
      messages = [ChatMessage("user", prompt)]
      async for chunk in client.chat(messages, stream=True):
          yield chunk
  ```
- **前端**：`fetch` + `ReadableStream` 解析，逐字渲染

#### 模块 4.4：选区 AI 重写

- **文件**：
  - `config/prompts/chapter_rewrite.yaml`
  - `server/src/api/chapters.py`（rewrite 接口）
- **流程**：
  ```
  用户选中文本 → 输入提示词 → 点击"AI 重写"
  → 前端调 API：{chapter_id, from, to, prompt}
  → 后端流式返回新内容
  → 前端替换选区
  → 自动保存版本
  ```
- **关键代码（前端）**：
  ```tsx
  async function rewriteSelection(editor: Editor, prompt: string) {
    const { from, to } = editor.state.selection;
    const original = editor.state.doc.textBetween(from, to);

    const newContent = await streamApi("/chapters/rewrite", {
      chapter_id: currentChapterId,
      original_text: original,
      user_prompt: prompt,
    });

    editor.chain().focus().setTextSelection({ from, to }).insertContent(newContent).run();

    // 自动保存版本
    await saveVersion(currentChapterId, "ai_rewrite", prompt);
  }
  ```

#### 模块 4.5：提示词框（始终显示）

- **文件**：
  - `apps/desktop/src/components/PromptBox.tsx`
- **设计**：
  - 悬浮在右侧或底部
  - 输入框 + 按钮
  - 灵感园：用于修改大纲
  - 创作：用于重新生成/重写

#### 模块 4.6：版本控制（核心）

- **文件**：
  - `server/src/core/versioning/version_tree.py`
  - `server/src/core/versioning/diff.py`
  - `server/src/api/chapters.py`（版本接口）
  - `apps/desktop/src/pages/Creation/VersionPanel.tsx`
  - `apps/desktop/src/components/DiffViewer.tsx`
- **关键代码 `version_tree.py`**：
  ```python
  from datetime import datetime
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import select
  from ..models.version import Version

  class VersionTree:
      def __init__(self, session: AsyncSession, entity_type: str, entity_id: int):
          self.session = session
          self.entity_type = entity_type
          self.entity_id = entity_id

      async def save_version(
          self,
          content: str,
          trigger: str,
          parent_id: int | None = None,
          prompt: str | None = None,
      ) -> int:
          # 计算 diff
          parent_content = None
          if parent_id:
              parent = await self.session.get(Version, parent_id)
              parent_content = parent.content
          diff = compute_diff(parent_content, content) if parent_content else None

          version = Version(
              entity_type=self.entity_type,
              entity_id=self.entity_id,
              parent_version_id=parent_id,
              content=content,
              diff=diff,
              trigger=trigger,
              prompt=prompt,
              metadata={"created_at": datetime.now().isoformat()},
          )
          self.session.add(version)
          await self.session.commit()
          return version.id

      async def list_versions(self) -> list[Version]:
          result = await self.session.execute(
              select(Version)
              .where(Version.entity_type == self.entity_type, Version.entity_id == self.entity_id)
              .order_by(Version.created_at.desc())
          )
          return list(result.scalars())

      async def rollback(self, version_id: int) -> int:
          """软回滚：把该版本内容设为当前内容，生成新版本"""
          target = await self.session.get(Version, version_id)
          if not target:
              raise ValueError(f"Version {version_id} not found")

          # 找到当前最新版本作为 parent
          latest = (await self.list_versions())[0]

          return await self.save_version(
              content=target.content,
              trigger="rollback",
              parent_id=latest.id,
              prompt=f"rollback_to:{version_id}",
          )
  ```
- **diff 库**：`diff-match-patch`
- **DiffViewer**：`react-diff-viewer-continued`

#### 模块 4.7：导出 md / word

- **文件**：
  - `server/src/services/export_service.py`
  - `server/src/api/export.py`
- **word 导出**：用 `python-docx` + 模板
- **关键代码**：
  ```python
  from docx import Document
  from docx.shared import Pt

  def export_to_word(chapters: list[Chapter], novel: Novel) -> bytes:
      doc = Document()
      doc.add_heading(novel.name, 0)

      for chapter in chapters:
          doc.add_heading(chapter.title, level=1)
          for para in chapter.content.split("\n\n"):
              doc.add_paragraph(para)

      buffer = io.BytesIO()
      doc.save(buffer)
      return buffer.getvalue()
  ```

#### 阶段 4 产出物

- [ ] 选择作品进入创作
- [ ] 流式生成章节
- [ ] 选区 AI 重写
- [ ] 全文重写
- [ ] 提示词框工作
- [ ] 版本控制完整
- [ ] diff 对比 + 回滚
- [ ] 导出 md/word

---

### Phase 5：质量检测（1.5 周）

#### 模块 5.1：检测范围选择

- **文件**：
  - `apps/desktop/src/pages/QualityCheck/RangeSelector.tsx`
  - `server/src/api/quality.py`

#### 模块 5.2：多维度并行评分

- **文件**：
  - `config/prompts/quality_*.yaml`（6 个维度）
  - `server/src/services/quality_service.py`
- **维度**：
  1. 文笔
  2. 逻辑
  3. 节奏
  4. 人设一致性 ⭐（基于人物卡）
  5. 题材合规性 ⭐（基于常识库）
  6. [题材特色]
- **关键代码（并行调用）**：
  ```python
  import asyncio

  async def evaluate_chapter(
      self,
      novel_id: int,
      chapter_id: int,
  ) -> QualityReport:
      chapter = await self.chapter_service.get(chapter_id)
      characters = await self.character_service.get_active_characters(novel_id)
      genre_config = load_genre_config(novel.genre)

      dimensions = ["writing", "logic", "pacing", "consistency", "genre"]

      # 并行调用
      tasks = [
          self._evaluate_dimension(dim, chapter, characters, genre_config)
          for dim in dimensions
      ]
      results = await asyncio.gather(*tasks)

      return QualityReport(
          chapter_id=chapter_id,
          total_score=sum(r.score for r in results) / len(results),
          dimension_scores={dim: r.score for dim, r in zip(dimensions, results)},
          issues=[issue for r in results for issue in r.issues],
          suggestions=[s for r in results for s in r.suggestions],
      )
  ```

#### 模块 5.3：人设一致性检测

- **文件**：
  - `config/prompts/quality_consistency.yaml`
  - `server/src/services/quality_service.py`（内嵌）
- **关键代码**：
  ```python
  async def _check_consistency(
      self,
      chapter: Chapter,
      characters: list[Character],
  ) -> DimensionResult:
      prompt = f"""
      请检查以下章节中人物行为是否与人物卡一致。

      # 人物卡
      {format_characters(characters)}

      # 章节内容
      {chapter.content}

      # 检查项
      1. 人物决策是否符合其"做事习惯"
      2. 人物对话是否符合其性格
      3. 是否有人物突然转变性格而未交代原因
      4. 人物关系是否前后一致

      # 输出 JSON
      ```json
      {{
        "score": 0-10,
        "issues": [
          {{"character": "姓名", "problem": "问题", "quote": "原文章节引用", "suggestion": "建议"}}
        ]
      }}
      ```
      """
      response = await self.llm.chat([ChatMessage("user", prompt)], temperature=0.3)
      result = json.loads(response.content)
      return DimensionResult(
          dimension="consistency",
          score=result["score"],
          issues=result["issues"],
      )
  ```

#### 模块 5.4：题材合规性检测

- **文件**：
  - `config/genres/xuanhuan.yaml`（常识库）
  - `config/prompts/quality_genre.yaml`
- **实现**：从常识库加载规则，注入 prompt，让 LLM 检查

#### 模块 5.5：报告生成 + UI

- **文件**：
  - `apps/desktop/src/pages/QualityCheck/Report.tsx`
  - 雷达图：recharts
- **关键组件**：
  - 总分（圆环）
  - 各维度分数（雷达图）
  - 问题列表（可点击跳转到段落）
  - 改进建议

#### 阶段 5 产出物

- [ ] 选择章节范围
- [ ] 多维度评分
- [ ] 题材合规性检测
- [ ] 人设一致性检测
- [ ] 报告可视化

---

### Phase 6：仓库（1 周）

#### 模块 6.1：灵感库列表 + 详情

- **文件**：
  - `apps/desktop/src/pages/Library/InspirationList.tsx`
  - `apps/desktop/src/pages/Library/InspirationDetail.tsx`
- **详情页内容**：
  - 基础信息
  - ⭐ 人物卡查看
  - ⭐ 大纲查看
  - 简要剧情
  - 灵感词记录
  - 操作（编辑/导出/进入创作/删除）

#### 模块 6.2：藏书馆列表 + 详情

- **文件**：
  - `apps/desktop/src/pages/Library/LibraryList.tsx`
  - `apps/desktop/src/pages/Library/LibraryDetail.tsx`
- **详情页**：
  - 章节列表
  - 章节查看
  - 版本历史入口
  - 导出

#### 模块 6.3：本地文件夹扫描 ⭐

- **文件**：
  - `server/src/core/scanner/novel_detector.py`
  - `server/src/core/scanner/novel_scanner.py`
  - `server/src/core/scanner/novel_importer.py`
  - `server/src/api/scanner.py`
  - `apps/desktop/src/pages/Library/ScannerConfig.tsx`
- **关键代码 `novel_detector.py`**：
  ```python
  import re
  from pathlib import Path
  from dataclasses import dataclass

  CHAPTER_PATTERNS = [
      re.compile(r"第[一二三四五六七八九十百千万\d]+章\s*[^\n]*"),
      re.compile(r"Chapter\s*\d+", re.IGNORECASE),
  ]

  @dataclass
  class DetectedNovel:
      dir_path: str
      title: str
      chapter_count: int
      total_words: int
      chapters: list[dict]  # [{"title": ..., "path": ..., "word_count": ...}]

  class NovelDetector:
      def is_novel_dir(self, path: str) -> bool:
          p = Path(path)
          if not p.is_dir():
              return False

          md_files = list(p.glob("*.md"))
          if len(md_files) < 3:
              return False

          # 检查文件命名
          for f in md_files[:5]:
              content = f.read_text(encoding="utf-8", errors="ignore")[:500]
              if any(p.search(content) for p in CHAPTER_PATTERNS):
                  return True

          return False

      def extract_metadata(self, path: str) -> DetectedNovel:
          p = Path(path)
          md_files = sorted(p.glob("*.md"))

          chapters = []
          total_words = 0
          for f in md_files:
              content = f.read_text(encoding="utf-8", errors="ignore")
              words = len(content)
              total_words += words

              # 提取章节标题
              title = f.stem
              for pattern in CHAPTER_PATTERNS:
                  match = pattern.search(content[:200])
                  if match:
                      title = match.group(0)
                      break

              chapters.append({
                  "title": title,
                  "path": str(f.absolute()),
                  "word_count": words,
              })

          return DetectedNovel(
              dir_path=str(p.absolute()),
              title=p.name,
              chapter_count=len(md_files),
              total_words=total_words,
              chapters=chapters,
          )
  ```
- **用户人工**：配置扫描目录 → 启动扫描 → 看到结果 → 确认导入

#### 模块 6.4：Skill 系统基础（提前）

- **文件**：
  - `server/src/core/skills/base.py`
  - `server/src/core/skills/registry.py`
  - `server/src/core/skills/builtin/word_counter.py`（先做 1-2 个）
  - `server/src/core/skills/builtin/sensitive_word.py`
  - `server/tests/test_skills.py`
- **关键代码 `base.py`**：
  ```python
  from typing import Protocol
  from dataclasses import dataclass, field
  from abc import abstractmethod

  @dataclass
  class SkillResult:
      success: bool
      data: dict = field(default_factory=dict)
      error: str | None = None

  class Skill(Protocol):
      name: str
      description: str
      input_schema: dict
      requires_llm: bool

      @abstractmethod
      async def execute(self, **kwargs) -> SkillResult:
          ...
  ```
- **关键代码 `word_counter.py`**：
  ```python
  from .base import Skill, SkillResult

  class WordCounterSkill:
      name = "word_counter"
      description = "统计文本字数（中英文混合）"
      input_schema = {
          "type": "object",
          "properties": {
              "text": {"type": "string", "description": "要统计的文本"}
          },
          "required": ["text"]
      }
      requires_llm = False

      async def execute(self, text: str) -> SkillResult:
          chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
          english = len([w for w in text.split() if w.isascii()])
          return SkillResult(
              success=True,
              data={"chinese_chars": chinese, "english_words": english, "total": chinese + english}
          )
  ```

#### 阶段 6 产出物

- [ ] 灵感库列表 + 详情完整
- [ ] 详情页可看人物卡和大纲
- [ ] 藏书馆列表 + 详情
- [ ] 本地扫描 + 接入
- [ ] 2-3 个基础 Skill 可用

---

### Phase 7：优化与 Skill 完善（1 周）

#### 模块 7.1：剩余 9 个 Skill

- `chapter_summarizer.py`
- `character_extractor.py`
- `plot_analyzer.py`
- `web_search.py`
- `read_local_file.py`
- `consistency_checker.py`
- `style_analyzer.py`
- `pacing_visualizer.py`
- `outline_structurer.py`
- `genre_classifier.py`

每个 Skill 按 `base.py` 接口实现。

#### 模块 7.2：Skill 市场 UI

- **文件**：
  - `apps/desktop/src/pages/Skills/index.tsx`
  - `apps/desktop/src/pages/Skills/SkillCard.tsx`
  - `apps/desktop/src/pages/Skills/CustomSkillForm.tsx`

#### 模块 7.3：错误处理 + 加载状态

- 全局错误边界
- API 错误提示 toast
- 加载骨架屏
- 按钮 disabled 状态

#### 模块 7.4：备份/恢复

- **文件**：
  - `server/src/services/backup_service.py`
  - 设置页加"导出/导入"
- **导出**：打包 `data/novels/` + `book-soul.db` 为 zip
- **导入**：解压并恢复

#### 阶段 7 产出物

- [ ] 全部 12 个预装 Skill 可用
- [ ] Skill 市场 UI 完整
- [ ] 错误处理优雅
- [ ] 备份/恢复可用

---

### Phase 8：打包与发布（1 周）

#### 模块 8.1：Tauri 打包配置

- **文件**：
  - `apps/desktop/src-tauri/tauri.conf.json`（配置 icons、bundle）
  - `apps/desktop/src-tauri/Cargo.toml`（release 配置）
- **步骤**：
  1. 设计应用图标（512x512 + 多尺寸）
  2. 配置 `tauri.conf.json` bundle
  3. 准备安装包信息

#### 模块 8.2：自动 Release

- **文件**：
  - `.github/workflows/release.yml`
- **关键代码**：
  ```yaml
  name: Release

  on:
    push:
      tags: ['v*']

  jobs:
    release:
      runs-on: ${{ matrix.os }}
      strategy:
        matrix:
          os: [windows-latest, macos-latest, ubuntu-latest]
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with: { node-version: '20' }
        - run: npm install -g pnpm
        - run: cd apps/desktop && pnpm install && pnpm tauri build
        - uses: softprops/action-gh-release@v2
          with:
            files: |
              apps/desktop/src-tauri/target/release/bundle/**/*.msi
              apps/desktop/src-tauri/target/release/bundle/**/*.exe
              apps/desktop/src-tauri/target/release/bundle/**/*.dmg
              apps/desktop/src-tauri/target/release/bundle/**/*.AppImage
  ```

#### 模块 8.3：README + 文档

- **文件**：
  - `README.md`（完善）
  - `docs/USER_GUIDE.md`
  - `docs/API.md`
  - `docs/ARCHITECTURE.md`

#### 阶段 8 产出物

- [ ] Windows .msi / .exe 可下载
- [ ] Mac .dmg（如果在 Mac 上 build）
- [ ] Linux .AppImage
- [ ] GitHub Release 自动发布
- [ ] README 完整

---

## 6. 质量门禁规范（必须）

### 6.1 Pre-commit 拦截

每次 commit 前自动运行：

1. **ruff format** —— 代码格式化
2. **ruff check** —— lint 检查
3. **gitleaks** —— 检查泄露 key
4. **check-yaml / check-json** —— 配置文件语法

**不通过 = 阻断 commit**。

### 6.2 CI 必跑

每个 push / PR：

1. ruff format --check
2. ruff check
3. pytest --cov（覆盖率 > 60%）
4. mypy src
5. 前端 tsc --noEmit
6. 前端 pnpm build

**不通过 = 红色 ✗**。

### 6.3 提交前必读

每次新对话开始，用户要先说：
> "请先运行 `pre-commit run --all-files` 和 `pytest`，确认全过再开始新功能。"

---

## 7. GitHub 自动同步规范

### 7.1 .gitignore 必须包含

```
# 隐私
.env
.env.*
!.env.example
data/
*.key
*.pem

# Python
__pycache__/
*.pyc
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
.vite/

# Tauri
apps/desktop/src-tauri/target/

# 系统
.DS_Store
Thumbs.db
```

### 7.2 提交流程

每次 Phase 模块完成后：

```bash
# 1. 跑质量门禁
pre-commit run --all-files
pytest
# 必须全过

# 2. 提交
git add .
git commit -m "Phase X 模块 Y: <描述>"

# 3. 推送
git push origin main

# 4. CI 跑通（在 GitHub Actions 页面查看）
```

### 7.3 发布流程

每完成一个 Phase：

```bash
git tag v0.X.0
git push origin v0.X.0
# GitHub Actions 自动 build + release
```

---

## 8. 重要提醒（agent 必读）

### 8.1 不允许做的事

- ❌ 不用 LangChain
- ❌ 不用 Flask / Django
- ❌ 不用 Electron
- ❌ 一次写超过 300 行代码（一个模块）
- ❌ 用 print 调试
- ❌ 写未经测试的业务代码
- ❌ 提交未通过 ruff 的代码
- ❌ 引用不存在的库或 API（必须先 Google 确认）
- ❌ 把 API Key 硬编码在代码里
- ❌ 跳过测试写新功能

### 8.2 必须做的事

- ✅ 写代码前先写测试
- ✅ 每次提交前跑 ruff + pytest
- ✅ 每个模块完成后输出"验证步骤清单"
- ✅ 区分代码验证和用户验证
- ✅ 长函数必须拆分
- ✅ 复杂逻辑加注释
- ✅ API 设计遵循 RESTful

### 8.3 写测试的规范

```python
# tests/test_character_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.character_service import CharacterService
from src.schemas.character import CharacterCreate

@pytest.mark.asyncio
async def test_create_character(session: AsyncSession):
    service = CharacterService(session)
    data = CharacterCreate(
        novel_id=1,
        name="张三",
        role="主角",
        personality="坚毅",
    )
    character = await service.create(data)
    assert character.id is not None
    assert character.name == "张三"
    assert character.current_version_id is not None

@pytest.mark.asyncio
async def test_update_growth(session: AsyncSession):
    # 创建人物
    # 更新 growth
    # 验证 growth_arc 追加
    # 验证版本数 +1
    ...
```

---

# 文档 2：USER_CHECKLIST.md（用户人工清单）

> 退出 Plan Mode 后，此文档将写入 `C:\Users\JZ\Desktop\Book Soul\USER_CHECKLIST.md`

## Part A：环境准备（一次性，约 1-2 天）

### A.1 系统要求

- **操作系统**：Windows 10/11（推荐）、macOS 12+、Ubuntu 20.04+
- **磁盘空间**：至少 5GB（开发环境 + 模型缓存）
- **内存**：至少 8GB（跑本地 LLM 建议 16GB+）

### A.2 必装工具清单

| 工具 | 版本 | 安装命令 | 验证命令 |
|------|------|----------|----------|
| **Python** | 3.11+ | https://www.python.org/downloads/ | `python --version` |
| **Node.js** | 20 LTS | https://nodejs.org/ | `node --version` |
| **pnpm** | 9+ | `npm install -g pnpm` | `pnpm --version` |
| **Rust** | stable | https://rustup.rs/ | `rustc --version` |
| **uv** | latest | `pip install uv` | `uv --version` |
| **Git** | 2.40+ | https://git-scm.com/ | `git --version` |
| **VS Code** | latest | https://code.visualstudio.com/ | - |
| **Visual Studio Build Tools** | 2022 | https://visualstudio.microsoft.com/downloads/（选"C++ build tools"工作负载） | - |

### A.3 可选工具

| 工具 | 用途 | 安装 |
|------|------|------|
| **Ollama** | 本地 LLM 推理 | https://ollama.com/ |
| **LM Studio** | 图形化本地 LLM | https://lmstudio.ai/ |

### A.4 安装后必须验证的 5 件事

打开 PowerShell 依次运行：

```powershell
python --version        # 应显示 3.11.x 或更高
node --version          # 应显示 v20.x.x
pnpm --version          # 应显示 9.x.x
rustc --version         # 应显示 rustc 1.xx.x
uv --version            # 应显示 uv 0.x.x
git --version           # 应显示 git version 2.4x.x
```

如果其中任何一个失败，**先解决再继续**。

### A.5 VS Code 推荐插件

- Python（Microsoft）
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Tauri
- GitLens
- Error Lens
- Chinese Language Pack（中文界面）

---

## Part B：账号与 API Key（约 1-2 天）

### B.1 GitHub 账号

- 注册：https://github.com/
- 创建 Personal Access Token（PAT）：
  - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
  - 勾选 `repo`, `workflow`
  - 保存到密码管理器

### B.2 LLM API Key

#### 主用：minimax-M3

- 注册：https://api.minimaxi.com/
- 申请 API Key
- 记录：`MINIMAX_API_KEY=sk-xxx`、`MINIMAX_BASE_URL=https://api.minimaxi.com/v1`

#### 备用：OpenAI / Anthropic（至少 1 个）

- OpenAI: https://platform.openai.com/
- Anthropic: https://console.anthropic.com/

### B.3 可选 Key

- **Tavily**（网络搜索）：https://tavily.com/
- **LangSmith**（调试）：https://smith.langchain.com/

### B.4 填入 .env

项目根目录创建 `.env`（**绝对不入 git**）：

```bash
# minimax
MINIMAX_API_KEY=sk-xxx
MINIMAX_BASE_URL=https://api.minimaxi.com/v1

# OpenAI（备用）
OPENAI_API_KEY=sk-xxx

# Tavily（可选）
TAVILY_API_KEY=tvly-xxx

# LangSmith（可选）
LANGSMITH_API_KEY=lsv2_xxx
LANGSMITH_TRACING=false
```

---

## Part C：素材准备（贯穿开发过程）

### C.1 质量检测测试样本

准备 5-10 本完整小说（任意题材）：

- 每本 ≥ 10 章
- 存到 `~/Documents/test-novels/`
- Phase 5 质量检测时使用

### C.2 词库参考

如有余力，可先收集（**按 JEE 决策的优先级**）：

- 修仙经典词条 800+（P0，最高优先级）
- 都市经典词条 500+（P1）
- 悬疑经典词条 500+（P2）
- 言情经典词条 500+（P3）
- Phase 3 词库系统时使用

### C.3 本地小说扫描

如果你电脑里已有小说：

- 整理路径到 `~/Documents/我的小说/`
- Phase 6 扫描接入时使用

---

## Part D：每次开发对话模板

### D.1 通用模板（新对话开头用）

```
我要做 Book Soul 项目（小说 AI 写作桌面应用）。

完整计划在项目根目录 PROJECT_PLAN.md 和 USER_CHECKLIST.md。

本次任务：
- 阶段：Phase X
- 模块：模块 X.Y
- 目标：<一句话目标>
- 验收标准：<怎么验证完成>

请：
1. 先读取 PROJECT_PLAN.md 中 Phase X 模块 X.Y 部分
2. 列出本模块要创建/修改的文件清单
3. 按计划逐步实施
4. 完成后运行 ruff + pytest + pre-commit
5. 给出我需要在 UI 或功能上人工验证的点
6. 给出 commit 消息建议
```

### D.2 bug 反馈模板

```
Phase X 模块 X.Y 出现 bug。

错误信息：
<粘贴完整错误>

复现步骤：
1. ...
2. ...

期望：...
实际：...

请：
1. 定位问题
2. 修复
3. 加测试防止回归
4. 验证修复
```

### D.3 续写提示

如果上次的对话太长/上下文满了，开新对话时：

```
继续 Book Soul 项目 Phase X 模块 X.Y 的开发。

上次进度：<简短描述>

请读取 PROJECT_PLAN.md，先确认本模块进度，然后继续。
```

---

## Part E：每个阶段的检验方法

### E.1 代码层面（agent 自动跑）

- `pre-commit run --all-files` —— 必须全过
- `pytest` —— 必须全过
- `ruff check .` —— 必须全过
- `mypy src` —— 警告可接受，错误不接受

### E.2 功能层面（用户必须测）

每个模块完成，agent 会列出"用户验证清单"，用户按清单手动测试：

| 模块 | 验证动作 |
|------|----------|
| Phase 0.3 | 浏览器打开 http://127.0.0.1:8765/docs 看到 Swagger |
| Phase 0.7 | 运行 `pnpm tauri dev` 看到窗口 |
| Phase 0.10 | 点击"测试 LLM"按钮看到真实回复 |
| Phase 1.1 | 用 curl 测试 /novels 接口 CRUD |
| Phase 3.3 | 选 5 个灵感词 → 生成 3 个剧情 → 看到结果 |
| Phase 4.3 | 点击"生成章节" → 看到流式输出（字一个个蹦出来） |
| Phase 4.4 | 选中一段 → 输入提示词 → AI 重写 → 内容替换 |
| Phase 4.6 | 修改内容 → 看版本历史 → 对比 → 回滚 |
| Phase 5.2 | 选章节 → 检测 → 看雷达图 + 问题列表 |
| Phase 6.3 | 配置扫描目录 → 看到检测到的小说 → 导入 |

### E.3 集成测试（贯穿）

- **数据流测试**：UI 操作 → 后端 → DB 写入 → 重新读出正确
- **错误处理测试**：断网、LLM 超时、key 错误时应用不崩
- **重启测试**：关闭应用再打开，数据还在

---

## Part F：常见问题

### F.1 启动报错 "ModuleNotFoundError"

**原因**：依赖没装
**解决**：`cd server && uv sync`

### F.2 pre-commit 拦截了 commit

**原因**：代码风格不对或泄露 key
**解决**：
```bash
# 看具体哪个 hook 失败
pre-commit run --all-files
# 修复后再 commit
```

### F.3 LLM 调用失败

**排查**：
1. `.env` 里 API Key 是否正确
2. 网络是否能访问 provider
3. 余额是否充足
4. 用 curl 单独测试：
   ```bash
   curl -X POST https://api.minimaxi.com/v1/chat/completions \
     -H "Authorization: Bearer $MINIMAX_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"MiniMax-M3","messages":[{"role":"user","content":"hi"}]}'
   ```

### F.4 Tauri 启动失败

**排查**：
1. Rust 是否装好
2. Visual Studio Build Tools 是否装（C++ 工作负载）
3. WebView2 是否装（Windows 11 自带，10 需要手动装）

### F.5 章节生成卡住

**排查**：
1. 人物卡是否合理（不能是空卡）
2. 大纲是否太短（至少一段话）
3. LLM provider 是否稳定
4. 日志：`tail -f data/logs/server.log`

### F.6 桌面应用打包失败

**排查**：
1. icon 是否准备
2. 平台工具链是否齐全
3. `tauri.conf.json` identifier 是否正确

### F.7 GitHub Actions 失败

**排查**：
1. 看具体哪个 step 失败
2. 本地重现：
   ```bash
   ruff check .
   pytest
   mypy src
   ```
3. 修复后 push 自动重跑

### F.8 提交时 gitleaks 报警

**说明**：可能你引用了某个看起来像 key 的字符串
**解决**：
- 如果是测试用的假 key，加 `# gitleaks:allow` 注释
- 如果是真的 key，**立即撤销** + 重新生成

---

## Part G：进度追踪

> 用户可复制这个 checklist 跟踪进度

### Phase 0：环境与基建
- [ ] 0.1 创建 GitHub 仓库
- [ ] 0.2 基础配置文件
- [ ] 0.3 Python 后端初始化
- [ ] 0.4 日志与配置
- [ ] 0.5 LLM 抽象层
- [ ] 0.6 数据库初始化
- [ ] 0.7 Tauri 桌面壳
- [ ] 0.8 质量门禁
- [ ] 0.9 GitHub Actions CI
- [ ] 0.10 Hello World 验证

### Phase 1：核心后端服务
- [ ] 1.1 作品 CRUD
- [ ] 1.2 人物卡 CRUD ⭐
- [ ] 1.3 章节 CRUD + 版本
- [ ] 1.4 大纲 CRUD
- [ ] 1.5 灵感库 CRUD
- [ ] 1.6 加密服务
- [ ] 1.7 记忆系统骨架

### Phase 2：桌面壳 + 前端骨架
- [ ] 2.1 路由与基础布局
- [ ] 2.2 shadcn/ui 集成
- [ ] 2.3 Tauri ↔ Python 通信
- [ ] 2.4 设置页基础
- [ ] 2.5 Zustand 状态管理

### Phase 3：灵感园 - 开新书
- [ ] 3.1 题材选择 + 词库
- [ ] 3.2 灵感词操作
- [ ] 3.3 简要剧情生成
- [ ] 3.4 完整版大纲生成
- [ ] 3.5 人物卡自动生成 ⭐
- [ ] 3.6 人物卡管理 UI
- [ ] 3.7 状态机实现
- [ ] 3.8 保存导出

### Phase 4：创作
- [ ] 4.1 作品选择
- [ ] 4.2 Tiptap 集成
- [ ] 4.3 章节生成（流式）
- [ ] 4.4 选区 AI 重写
- [ ] 4.5 提示词框
- [ ] 4.6 版本控制
- [ ] 4.7 导出 md/word

### Phase 5：质量检测
- [ ] 5.1 检测范围选择
- [ ] 5.2 多维度并行评分
- [ ] 5.3 人设一致性
- [ ] 5.4 题材合规性
- [ ] 5.5 报告 UI

### Phase 6：仓库
- [ ] 6.1 灵感库
- [ ] 6.2 藏书馆
- [ ] 6.3 本地文件夹扫描 ⭐
- [ ] 6.4 Skill 系统基础

### Phase 7：优化与 Skill 完善
- [ ] 7.1 剩余 9 个 Skill
- [ ] 7.2 Skill 市场 UI
- [ ] 7.3 错误处理
- [ ] 7.4 备份恢复

### Phase 8：打包与发布
- [ ] 8.1 Tauri 打包配置
- [ ] 8.2 自动 Release
- [ ] 8.3 文档完善

---

## Part H：开发节奏建议

按 1-2 小时/天 vibe coding：

- **每天 1 个模块**（约 100-200 行代码）
- **每周 5 个模块**
- **8-10 周完成全部**

**不要赶进度**：
- 每个模块完成后**先在 UI 验证**，再开下一个
- 遇到问题**先解决**，不要跳过
- 每周回顾一次进度，调整计划

---

# 总结

这份计划的核心设计：

1. **严格分模块**：每个模块 < 300 行代码，可独立开发/验证/提交
2. **强质量门禁**：pre-commit + CI + gitleaks 拦截
3. **清晰的用户边界**：用户只负责环境、Key、UI 验证；agent 负责代码
4. **标准化对话模板**：用户每次只需说"继续 Phase X 模块 Y"
5. **详细到具体文件**：每个模块有完整文件清单和关键代码
6. **覆盖所有 4 大功能 + 5 大子系统**：灵感园、创作、质量检测、仓库 + 人物卡、Skill、状态机、记忆、版本

**退出 Plan Mode 后**，我会立即把以下文件写入工作目录：

1. `C:\Users\JZ\Desktop\Book Soul\PROJECT_PLAN.md`（本文档的"文档 1"部分）
2. `C:\Users\JZ\Desktop\Book Soul\USER_CHECKLIST.md`（本文档的"文档 2"部分）
3. `C:\Users\JZ\Desktop\Book Soul\AGENTS.md`（项目规范）
4. `C:\Users\JZ\Desktop\Book Soul\.gitignore`
5. `C:\Users\JZ\Desktop\Book Soul\.env.example`
6. `C:\Users\JZ\Desktop\Book Soul\.gitleaks.toml`
7. `C:\Users\JZ\Desktop\Book Soul\.pre-commit-config.yaml`
8. `C:\Users\JZ\Desktop\Book Soul\SECURITY.md`
9. `C:\Users\JZ\Desktop\Book Soul\LICENSE` (MIT)
10. `C:\Users\JZ\Desktop\Book Soul\README.md`（初版）

**未解决的关键问题**（你退出 Plan Mode 前最好确认）：

1. ✅ **题材优先级**（v1.1 已确认）：修仙 → 都市 → 悬疑 → 言情
2. ✅ **minimax-M3 上下文窗口**（v1.1 已确认）：1M tokens
3. ✅ **用户自定义模型警告机制**（v1.1 已确认）：在模块 0.5 实现
4. **GitHub 仓库名**：建议 `book-soul`，需要你确认
5. **是否需要本对话直接开 Phase 0 编程**：你审核完计划后告诉我
