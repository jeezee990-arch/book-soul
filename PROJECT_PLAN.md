# Book Soul 项目计划书

> **文档状态：历史快照 + 决策记录**（2026-10-30 精简）
>
> 本文件**不再是施工图**。Phase 0–8 已全部落地，代码本身就是实现的唯一事实来源
> （逐模块的施工步骤、文件清单、验证点已于 2026-10-30 删除 —— 它们已过期且与代码重复）。
>
> | 你想知道 | 去哪看 |
> |---|---|
> | 现在能做什么、还差什么 | [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) §10 路线图 |
> | 每个目录干什么 | [docs/PROJECT_STRUCTURE.md](./docs/PROJECT_STRUCTURE.md) |
> | 怎么启动、怎么验证 | [docs/START_GUIDE.md](./docs/START_GUIDE.md) |
> | 出问题了怎么查 | [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) |
> | 界面长什么样 | [docs/DESIGN.md](./docs/DESIGN.md) |
>
> 保留在本文件里的，是**代码里看不出来的东西**：核心设计决策、明确不做的事、
> 模块完成状态、agent 协作方式。

---

## 1. 核心设计决策（不再变动）

| 项 | 决策 |
|---|---|
| 桌面壳 | Tauri 2（Rust） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + Tiptap 3 |
| 后端 | Python 3.11+ + FastAPI（async） |
| ORM / 数据库 | SQLAlchemy 2 + SQLite（aiosqlite，外键约束**必须显式开启**） |
| LLM 抽象 | 自研 Protocol（~200 行），**不用** LangChain / LlamaIndex |
| 包管理 | uv（Python）+ pnpm（Node） |
| 核心特色 | 人物卡驱动一致性 + Skill/Tool 系统 + 双模式 LLM（云端 + 本地 Ollama） |
| 部署 | 纯本地，无账号系统；数据存用户可指定目录 |
| 发布 | GitHub 公开仓库 + 独立版便携目录 + NSIS 安装包 |

### 1.1 向量库：**已移除**（2026-10-22）

早期设计里的 **ChromaDB / RAG 已彻底移除**。

- 原因：对个人网文收益低（要 50+ 章才体现）、负担重（embedding 依赖 + 向量库 + 检索调优）
- 替代方案：「人物卡 + 最近 3 章摘要 + 上一章尾部」的滑动窗口
- 代码里**没有** `chroma/` / `vector_store/` / `rag_memory` —— 别再重建它们

> ⚠️ 本文件早期版本把 ChromaDB 列为核心设计决策，与 §1.1 自相矛盾，
> 已于 2026-10-30 修正。

### 1.2 关键非目标（明确不做）

- ❌ 用户账号系统
- ❌ 主密码 / 密码派生
- ❌ 云端同步
- ❌ 多人协作
- ❌ LangChain 重型框架
- ❌ Electron

### 1.3 JEE 指定的开发期决策

- **题材优先级**：修仙 → 都市 → 悬疑 → 言情（从左到右依次递减）
- **辅助开发模型上下文**：1M tokens
- **用户自定义模型警告**：配置的模型不支持 1k-8k 每章生成时，UI 弹提醒

### 1.4 用户偏好（2026-10-23 UI 重设计时确认）

- **简洁优先**，但**功能一个不能少** —— 每个已有功能都要有可达入口
- agent 可以主动提出删改建议，不要只做加法
- 交付物要含**实际 UI 效果图**（不是文字描述）

---

## 2. 功能模块完成状态

Phase 0–8 **全部完成**。下表是模块清单与现状代码位置的对照，
用于「代码有没有漏实现某个模块」的逐项核对。

### Phase 0 · 环境与基建 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 0.1 GitHub 仓库 | ✅ | — |
| 0.2 基础配置文件 | ✅ | `.gitignore` `.gitleaks.toml` `.pre-commit-config.yaml` `pyproject.toml` |
| 0.3 Python 后端初始化 | ✅ | `server/src/main.py` `server/src/db.py` |
| 0.4 日志与配置 | ✅ | `server/src/core/logging.py` `server/src/core/config.py` `config/app.yaml` |
| 0.5 LLM 抽象层 | ✅ | `server/src/core/llm/`（base / factory / openai_compat / ollama） |
| 0.6 数据库初始化 | ✅ | `server/src/models/`（7 张表）+ `db.py` 的 schema 自愈 |
| 0.7 Tauri 桌面壳 | ✅ | `apps/desktop/src-tauri/`（lib / sidecar / logging） |
| 0.8 质量门禁 | ✅ | `.pre-commit-config.yaml`（ruff + gitleaks） |
| 0.9 GitHub Actions CI | ✅ | `.github/workflows/ci.yml`（backend / frontend / packaging-smoke） |
| 0.10 端到端验证 | ✅ | `server/tests/` 781 个用例 |

### Phase 1 · 核心后端服务 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 1.1 作品 CRUD | ✅ | `api/novels.py` `services/novel_service.py` |
| 1.2 人物卡 CRUD ⭐ | ✅ | `api/characters.py` `services/character_service.py` `character_generator.py` |
| 1.3 章节 CRUD + 版本 | ✅ | `api/chapters.py` `chapter_versioning.py` `core/versioning/` |
| 1.4 大纲 CRUD | ✅ | `api/outlines.py` `services/outline_*.py`（9 个模块） |
| 1.5 灵感库 CRUD | ✅ | `api/inspirations.py` `services/inspiration_service.py` |
| 1.6 加密服务 | ✅ | `core/security/`（dpapi / secret_store / encryption / keyring） |
| 1.7 记忆系统骨架 | ❌ **已移除**（2026-10-30） | 随 RAG + 聊天功能整块删除 |

### Phase 2 · 桌面壳 + 前端骨架 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 2.1 路由与基础布局 | ✅ | `apps/desktop/src/App.tsx` + `components/app-shell.tsx`（52px 顶栏 + 56px 图标栏） |
| 2.2 shadcn/ui 集成 | ✅ | `components/ui/`（10 个原子组件）+ `styles.css` 令牌 |
| 2.3 Tauri ↔ Python 通信 | ✅ | `src-tauri/src/sidecar.rs`（随机端口 / 就绪握手）+ `api/backend.ts` |
| 2.4 设置页基础 | ✅ | `pages/Settings/`（4 个分区） |
| 2.5 Zustand 状态管理 | ✅ | `stores/`（7 个 store，`workspace-store.ts` 持有全局唯一作品） |

### Phase 3 · 开新书 ✅

> 原名「灵感园」，2026-10 UI 重设计后收敛为**三步向导**：种子 → 剧情 → 大纲与人物。

| 模块 | 状态 | 位置 |
|---|---|---|
| 3.1 种子步（题材 + 词库） | ✅ | `pages/NewBook/seed-step.tsx` + `wordbank-manager-*.tsx` |
| 3.2 剧情步 | ✅ | `pages/NewBook/plot-step.tsx` + `use-plot-stream.ts` |
| 3.3 大纲步 | ✅ | `pages/NewBook/outline-step.tsx` + `use-outline-stream.ts` |
| 3.4 三步流程骨架与导航 | ✅ | `pages/NewBook/index.tsx` + `use-newbook-flow.ts` |
| 3.5 人物卡自动生成 ⭐ | ✅ | `services/character_generator.py` + `use-character-stream.ts` |
| 3.6 人物卡管理 UI | ✅ | `pages/Writing/tabs/character-tab.tsx` |
| 3.7 状态机实现 | ❌ **已移除**（2026-10-30） | 后端状态机是另一套并行实现，留着会误导；实际由前端 Zustand 编排 |
| 3.8 保存到灵感库 + 导出 | ✅（导出为作品级） | `api/inspirations.py` + `api/export.py`（md / html / docx） |
| 3.9 全局 UI + 静态框架 | ✅ | 见 [docs/DESIGN.md](./docs/DESIGN.md) |

### Phase 4 · 写作 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 4.1 章节树 + 列表 | ✅ | `pages/Writing/chapter-tree.tsx`（244px） |
| 4.2 Tiptap 集成 | ✅ | `pages/Writing/editor-pane.tsx` + `styles.css` 的 `.novel-paper` |
| 4.3 章节生成（流式） | ✅ | `api/chapter_generation.py` + `services/chapter_generator.py` + `use-chapter-stream.ts` |
| 4.4 选区 AI 重写 | ✅ | `services/chapter_rewriter.py` + `pages/Writing/tabs/rewrite-tab.tsx` |
| 4.5 提示词框 | ✅ | `pages/Writing/tabs/generate-tab.tsx` |
| 4.6 版本控制 | ✅ | `core/versioning/` + `pages/Writing/tabs/version-tab.tsx` |
| 4.7 导出 md / word | ✅ | `services/export_service.py` + `export_docx.py` |

### Phase 5 · 质检 ❌ 已移除

> 2026-10-30：质检模块**整体下线**（用户指令「把质检模块删掉」）。
> 后端 API / service / prompt / 路由、前端 Tab / 按钮、“质检 → 重写”闭环全部删除。
> 质检原本**不落库**（不存历史报告），无需数据迁移或 DROP 表。
> 下表保留为历史记录。

| 模块 | 状态 | 位置 |
|---|---|---|
| 5.1 检测范围选择 | ❌ **已移除** | 原 `pages/Writing/tabs/quality-tab.tsx` |
| 5.2 多维度并行评分 | ❌ **已移除** | 原 `services/quality_service.py`（5 维度 `asyncio.gather`） |
| 5.3 人设一致性 | ✅ 保留 | `core/skills/builtin/consistency_checker.py` + `core/chapter_context.py`（与质检无关） |
| 5.4 题材合规性 | ❌ **已移除** | 原 `config/prompts/quality_genre.yaml`（`config/genres/` 题材常识库本身保留） |
| 5.5 报告 UI | ❌ **已移除** | 原 `quality-tab.tsx`（横向评分条） |

### Phase 6 · 素材库 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 6.1 灵感库列表 + 详情 | ✅ | `pages/Library/InspirationList.tsx` / `InspirationDetail.tsx` |
| 6.2 藏书馆列表 + 详情 | ❌ **已移除** | 素材库重构为 作品 / 灵感 / 导入 三 Tab，藏书馆被「作品」Tab 取代 |
| 6.3 本地文件夹扫描 ⭐ | ✅ | `core/scanner/` + `pages/Library/ScannerConfig.tsx` |
| 6.4 Skill 系统基础 | ✅ | `core/skills/`（base / registry / manager / loader） |

### Phase 7 · 优化与 Skill 完善 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 7.1 12 个内置 Skill | ✅ | `core/skills/builtin/`（12 个） |
| 7.2 Skill 市场 UI | ❌ **已移除** | 降级为「设置 → AI 增强」分区 |
| 7.3 错误处理 + 加载状态 | ✅ | `components/ErrorBoundary.tsx` + `components/ui/` |
| 7.4 备份 / 恢复 | ✅ | `api/backup.py` + `services/backup_service.py` |

### Phase 8 · 打包与发布 ✅

| 模块 | 状态 | 位置 |
|---|---|---|
| 8.1 Tauri 打包配置 | ✅ | `src-tauri/tauri.conf.json` + `scripts/build_standalone.ps1` |
| 8.2 自动 Release | ✅ | `.github/workflows/release.yml` |
| 8.3 README + 文档 | ✅ | `README.md` + `docs/`（8 份） |

### 未启动 · Phase 9+（待规划）

- 协作编辑（WebSocket / Yjs CRDT）
- 多模态（图像 / 音频输入）
- 智能体（Agent）模式（自动多步任务）
- 浏览器扩展（从网页提取灵感）
- 移动端（Tauri Mobile）

> 详见 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) §10。

---

## 3. agent 协作方式

### 3.1 新会话开头

每个新会话先做这三件事，**不要问用户已经能查到的信息**：

1. 读 `AGENTS.md`（技术规范）+ `DEVELOPMENT_CONSTRAINTS.md`（行为约束）
2. 跑一次现状核对：`git status` + `git log --oneline -5`
3. 报告当前进度 / 下一个待办 / 阻塞项

### 3.2 通用模板

```
请先运行 `pre-commit run --all-files` 和 `pytest`，确认全过再开始新功能。
```

### 3.3 bug 反馈模板

```
现象：<看到什么>
预期：<应该怎样>
复现步骤：1. ... 2. ... 3. ...
日志：<贴 server.log 相关行>
```

### 3.4 修改计划书的模板

```
我看了 PROJECT_PLAN.md，想调整：<哪个模块>
原因：<为什么>
影响：<哪些下游要跟着改>
```

> 改计划书**必须先探讨**（`DEVELOPMENT_CONSTRAINTS.md` §1.3）。

### 3.5 模块开发流程

1. **测试先行**（如适用）：先写 `test_xxx.py`
2. **实现代码**：`src/xxx.py`
3. **本地验证**：`pytest` + `ruff check` + `ruff format --check`
4. **commit**：清晰消息（用户确认后）
5. **用户验证**：给用户「用户验证清单」

---

## 4. 质量门禁

### 4.1 Pre-commit（本地，阻断 commit）

1. `ruff format` —— 格式化
2. `ruff check` —— lint
3. `gitleaks` —— 密钥泄露扫描
4. `check-yaml` / `check-json` —— 配置语法

### 4.2 CI（GitHub Actions，每个 push / PR）

| Job | 内容 |
|---|---|
| `backend` | `ruff format --check` + `ruff check` + `pytest --cov` + `mypy`（非阻塞） |
| `frontend` | `pnpm test`（vitest）+ `pnpm build` + `cargo check` |
| `packaging-smoke` | 真打 sidecar → 启动 → 探活 → 检查数据目录 |

覆盖率目标：整体 ≥ 70%，核心模块 ≥ 80%。

### 4.3 提交流程

```bash
pre-commit run --all-files    # 必须全过
pytest
git add <明确的文件>          # 不要 git add .
git commit -m "Phase X 模块 Y: <描述>"
git push origin main
```

### 4.4 发布流程

```bash
git tag v0.X.0
git push origin v0.X.0        # GitHub Actions 自动 build + release
```

---

## 5. agent 必读：不允许 / 必须

> 技术规范的**唯一来源**是 [AGENTS.md](./AGENTS.md)。本节只列最常踩的几条。

### ❌ 不允许

- 不用 LangChain / LlamaIndex
- 不用 Flask / Django
- 不用 Electron
- 不用 `print` 调试（用 loguru）
- 流式调用用 `client.post()`（必须 `client.stream()`）
- 业务层直接 import httpx / LLM SDK
- 写 `_find_repo_root()`（路径统一走 `core/paths.py`）
- SQL 用字符串拼接
- 引用未确认的库 / API
- 跳过测试写新功能
- 把 API Key 硬编码进代码
- 提交未通过 ruff 的代码

### ✅ 必须

- 写代码前先写测试
- 每次提交前跑 ruff + pytest
- 每个模块完成后输出「用户验证清单」
- 区分**代码验证**（agent 跑）和**用户验证**（用户在 UI 跑）
- 复杂逻辑加注释（docstring 必填）
- API 设计遵循 RESTful

---

## 6. 修订记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 | 2026-09-02 | 初始计划书（Phase 0-9 完整施工图，3187 行） |
| v1.1 | 2026-09-02 | 初始确认版（题材优先级、辅助模型 1M 上下文、模型警告机制） |
| v1.2 | 2026-09-04 | 灵感园三步流程重构（模块 3.1-3.4 重新定义） |
| **v2.1** | **2026-10-30** | **质检模块整体下线**：Phase 5 标记为已移除；后端 API / service / prompt / 路由、前端 Tab / 按钮、“质检 → 重写”闭环全部删除；写作页右栏 6 Tab → 5 Tab；质检原不落库，无需数据迁移 |
| **v2.0** | **2026-10-30** | **精简为历史快照**：<br>· 删除约 2500 行逐模块施工步骤（已落地，代码即事实）<br>· 删除尾部 434 行 `USER_CHECKLIST.md` 重复副本（已独立成 `docs/TROUBLESHOOTING.md`）<br>· 修正 ChromaDB 矛盾表述（原写为核心决策，实际已移除）<br>· 模块清单改为「状态 + 代码位置」对照表，标注 3 个已移除模块<br>· 修正本机绝对路径 → `<仓库根>`<br>· 删除与 `AGENTS.md` 冲突的「单次不超过 300 行」限制<br>· 质量门禁改为对齐 `.github/workflows/ci.yml` 实际内容 |
