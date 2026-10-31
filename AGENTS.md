# AGENTS.md - Book Soul 项目规范

<!--
修改记录
- 2026-10-30：第十三轮（质检模块整体下线）。主要变化：
  · 删除质检模块全部代码：`api/quality.py`、`schemas/quality.py`、`services/quality_service.py`、
    `core/quality/`（含 prompts.py）、前端 `api/quality.ts` 与 `pages/Writing/tabs/quality-tab.tsx`、
    `server/tests/test_quality_service.py`、`config/prompts/quality_*.yaml`（5 个）
  · 质检**不落库**（旧实现明确「不存历史报告」）→ 无需 DROP 表、无需数据备份
  · 写作页右栏 6 Tab → 5 Tab（生成 / 重写 / 人物 / 大纲 / 版本）；编辑器顶部「质检」快捷按钮删除
  · 「质检 → 重写」闭环整体移除（`book-soul:rewrite-hint` CustomEvent 一并删）
  · `config/llm.yaml` 的 `routing` 删除 6 个 quality_* 场景；`skills/manager.py` 去掉 `quality_check` 场景
  · **保留** `quality_tier`（模型规格的质量档位字段，与质检无关）与 `config/genres/`（题材常识资产）
  · 文档同步：README / USER_GUIDE / API / ARCHITECTURE / DESIGN / PROJECT_STRUCTURE / SKILLS
- 2026-10-30：第十二轮（正文排版与字数口径 —— 用户实测的重大质量事故）。主要变化：
  · §4.11 新增「正文排版与字数口径」四条铁律：
    字数 = 非空白字符数（禁用 len()）/ 编辑器追加要插进最后一个段落内部 /
    正文必须过 ProseFormatter 兜底断段 / 正文是纯文本不是 HTML
  · 新增 `server/src/core/prose_format.py`：增量排版器（去汉字间空格、段落分隔、
    兜底断段、对白另起段）+ 统一字数口径
  · `chapter_generator` / `chapter_rewriter` 接入排版器；`chapter_service._word_count`
    从 `len()` 改为真实字数
  · `config/prompts/chapter_generation.yaml` v2：强化「必须分段 / 对话独立成段 /
    汉字之间不加空格 / 不少于目标字数」
  · MD / HTML 导出补上章节正文（原来只有大纲+人物卡，与 Word 导出不一致）
  · 导出章节标题去重：标题自带「第 N 章」时不再叠前缀
    （`export_service.chapter_heading()`，避免「第 1 章 · 第一章 xxx」）
  · 新增 `scripts/repair_chapter_paragraphs.py`：修复被假段落破坏的历史章节
    （默认模式重排假段落；`--split-dialogue` 保留段落划分只拆连续对白）
  · 排版器新增「连续对白强制断段」：引号**以句末标点收尾**才拆
    （`“甲？”“乙。”` 拆；`将“沈”“砚”二字` 不拆 —— 引用不能拆断）
- 2026-10-30：第十一轮（命名 + 素材库管理能力）。主要变化：
  · §6.1 新增「作品名唯一」数据完整性铁律 —— 素材库里同一时间只能有一本同名作品；
    禁止按名字 upsert 作品（那正是"新书存不进素材库 + 旧书被覆盖"的根因）
  · 大纲生成改为**靠 id 区分**「重生成同一本」与「新建一本」：
    传 `novel_id` → 复用该本；不传 → 新建且名字唯一（撞名自动加序号）
  · 作品新增 `sort_order`（手动顺序，持久化在后端）+ `POST /novels/reorder`
  · 开新书第 1 步加**书名输入框**（重名自动加序号，不覆盖旧书）
  · 素材库「作品」Tab 补齐管理能力：右键菜单（重命名 / 删除 / 上移下移 / 导出）、
    排序下拉、删除确认；作品卡拆成 `NovelCard.tsx`（新增可见的「⋯」入口 + 键盘菜单路径）
  · 前端 `ApiError` 补 `status` 字段（区分 409 与其它错误）
- 2026-10-30：第十轮（仓库清理 + 文档重整）。主要变化：
  · 删除 `docs/ui-redesign/`（2026-10 的 UI 重设计提案 + 16 张 mockup 图 + prototype.html，
    共 2.34 MB）—— 提案的视觉规范与实现**不一致**（色板方案未落地，实为 shadcn/ui zinc 灰阶），
    留着会误导人。现行规范改为 `docs/DESIGN.md`（全部按代码实测重写）
  · 5 张真机截图提升为 `docs/screenshots/`（真实界面，当前有效）
  · `USER_CHECKLIST.md` → `docs/TROUBLESHOOTING.md`（只留排障 + 应急，砍掉进度追踪与对话模板）
  · `PROJECT_PLAN.md` 精简为历史快照（3187 行 → 约 300 行），修正 ChromaDB 矛盾表述
  · `.env.example` 按 `config/llm.yaml` 真实 provider 重写（补 mimo，删代码里不存在的
    Anthropic/Tavily/LangSmith，web_search 实际用 SerpAPI）
  · `SECURITY.md` 修正数据目录路径、漏洞报告方式、第三方 provider 列表
  · 删除 8 个冗余 `.gitkeep`（目录里已有实际文件）
- 2026-10-30：第九轮（文档同步 + 推送）。主要变化：
  · 新增 §2.2「用户可见文档必须跟 UI 同步」
    —— README / USER_GUIDE 描述的是重设计**之前**的 6 项导航，
      实际早已改成 4 项（写作 / 开新书 / 素材库 / 设置），文档比代码更落后
  · 新增 docs/PROJECT_STRUCTURE.md（目录职责 + 数据流 + 修改指引 + 产物体积）
  · README 按当前结构重写（快速启动三方式 + 项目结构树 + 界面结构表）
  · START_GUIDE / USER_GUIDE 同步页面名与实测用例数（766 后端 + 213 前端）
- 2026-10-30：第八轮（清理死代码）。主要变化：
  · 删除 `core/memory/`（project_memory / rag_memory / conversation_memory）
    —— RAG 已移除后剩的空壳 + 聊天功能移除后的孤儿，业务零引用
  · 删除 `core/workflow/`（state_machine / new_book）—— 开新书三步流程
    实际由前端 Zustand 编排，后端状态机是另一套并行实现，留着会误导
  · 一并删除只测自己的 test_memory.py / test_state_machine.py
  · §2 目录约定同步删掉这两行 —— **别再重建它们**
- 2026-10-29：第七轮（质检续：外键 / 孤儿数据 / 里程碑保序）。主要变化：
  · db.py 开启 SQLite 外键约束（默认是关的 → ondelete="CASCADE" 形同虚设，
    删作品留孤儿；SQLite 又会复用被删的 id → 旧章节串进新作品）
  · db.py 启动时清理"父行已删"的孤儿行（CASCADE 删行 / SET NULL 置空）
  · §4.7 补：失败版本（error 事件）也要参与里程碑保序，
    否则后续版本的完成事件被压到整条流结束才吐
- 2026-10-29：第六轮（七项 UI 需求 + 质检）。主要变化：
  · §4.7 修正「并行保序」：内容实时透传 + 里程碑保序（`merge_queue_events_milestone_ordered`），
    明确禁用严格保序（`merge_queue_events_ordered`）—— 它就是「憋着最后一口气输出」的元凶
  · 新增 §4.10（流式失败两类）+ §4.9（同一帧别读刚 set 的 state）已在上一轮补齐
- 2026-10-24：第五轮（真机 UI 走查 + 门禁补漏）。主要变化：
  · §4.10 流式失败有两类（transport / server），前端必须都认，否则界面永远转圈
  · 根 pyproject.toml 的 ruff 排除 server/alembic/versions（模板生成文件不手改）
  · 新增 scripts/mock_provider.py（无 API Key 也能走完"开新书"三步）
- 2026-10-24：第四轮（用户实测反馈 5 条：深色滚动条 / 生成顺序 / 卡片不可滚 / 假流式 / 性能）。
  主要变化：
  · §4.7 流式端点三条铁律（思考不丢 / 容器可滚 / 并行保序）
  · §4.8 并行 LLM 调用 + 单 Session 写库（AsyncSession 并发写会炸）
  · §4.9 同一帧里不要读刚 set 的 state（setState 异步 → 选 B 生成 A）
  · 性能结论写进 §4.7：代码侧开销 +0.5ms/token，慢在模型不在代码
- 2026-10-22：重构版规范（用户授权全面重设）。主要变化：
  · 删除"单一函数 ≤ 200 行"，改为"单文件 ≤ 500 行 + docstring 必填 + 覆盖率门槛"
  · 删除 ChromaDB（代码里从未落地，RAG 对个人网文收益低、负担重）
  · mypy 保留但限定范围（src/core + src/services），CI 先警告不阻塞
  · 新增「桌面化与打包规范」「LLM 调用规范」「性能预算」
  · 新增硬门槛：流式契约测试 / 首字延迟预算 / 启动预算 / 打包冒烟
  · API Key 存储改为 DPAPI 加密文件（环境变量仍最高优先级）
- 2026-09-03：用户授权，添加 [DEVELOPMENT_CONSTRAINTS.md] 链接（顶部 + 参考资料）
-->

> 这是项目根目录的强制规范文件。所有参与本项目的 agent（minimax code 等）必须遵守。
>
> 📌 配套**行为约束**（沟通、流程、决策、agent 工作流）见 [DEVELOPMENT_CONSTRAINTS.md](./DEVELOPMENT_CONSTRAINTS.md)。本文件管"技术规范"，那文件管"行为约束"，**两者互补不替代**。

## 项目概述

**Book Soul** - 小说 AI 写作桌面应用
- 帮助网文/严肃文学作者从灵感发现到章节创作的全流程
- 核心特色：人物卡驱动一致性 + Skill/Tool 系统 + 双模式 LLM（云端 + 本地 Ollama）
- 部署：**Tauri 桌面应用**（自带 Python 后端，双击即用）+ GitHub 公开仓库
- 工作目录：`C:\Users\JZ\Desktop\Book Soul`

---

## 1. 技术栈（强制）

| 层级 | 技术 | 禁止替代 |
|------|------|----------|
| 桌面壳 | Tauri 2（Rust） | ❌ Electron |
| 前端框架 | React 18 + TypeScript + Vite | ❌ Vue / Svelte |
| 状态管理 | Zustand | ❌ Redux |
| UI 库 | shadcn/ui + Tailwind CSS | - |
| 编辑器 | Tiptap | ❌ Slate / Lexical |
| 后端 | Python 3.11+ + FastAPI | ❌ Flask / Django |
| ORM | SQLAlchemy 2 | ❌ Tortoise ORM |
| 数据库 | SQLite + aiosqlite | ❌ PostgreSQL |
| LLM 抽象 | 自研 Protocol（~200 行） | ❌ LangChain / LlamaIndex |
| Python 包管理 | uv | ❌ pip / poetry |
| Node 包管理 | pnpm | ❌ npm / yarn |
| 后端打包 | PyInstaller | - |
| 加密 | cryptography.Fernet（可选） | - |
| API Key 存储 | 环境变量 > DPAPI 加密文件 > 系统 Keyring | ❌ 明文 .env 进分发目录 |
| Lint | ruff | ❌ flake8 / black |
| 类型检查 | mypy（限定 src/core + src/services） | - |
| 测试 | pytest | - |
| Pre-commit | pre-commit + ruff + gitleaks | - |
| CI | GitHub Actions | - |

> **已移除**：ChromaDB / 向量数据库 —— 代码里从未落地，且 RAG（向量检索）对个人网文
> 收益低（要 50+ 章才体现）、负担重（embedding 依赖 + 向量库 + 检索调优）。
> 当前用「人物卡 + 最近 3 章摘要 + 上一章尾部」的滑动窗口策略，够用。

---

## 2. 目录约定

```
book-soul/
├── apps/desktop/                # Tauri + React 前端
│   ├── src/
│   │   ├── api/                 # 后端 API 封装（backend.ts 管地址/就绪）
│   │   ├── components/          # 通用组件（ui/ 是 shadcn 原子组件）
│   │   ├── pages/               # 4 个主页面（写作/开新书/素材库/设置）
│   │   ├── stores/              # Zustand 状态
│   │   ├── lib/  config/  types/
│   ├── src-tauri/
│   │   ├── src/lib.rs           # 桌面壳：Tauri command / 窗口事件 / 应用装配
│   │   ├── src/sidecar.rs       # 后端定位与拉起：端口 / 数据目录 / sidecar 路径 / 子进程
│   │   ├── src/logging.rs       # 桌面端日志（release 无控制台，eprintln! 会丢）
│   │   ├── tauri.conf.json
│   │   ├── binaries/            # sidecar 构建产物（gitignore）
│   │   └── Cargo.toml
├── server/
│   ├── src/
│   │   ├── api/                 # 路由层（依赖注入 + 错误映射）
│   │   ├── core/                # 基础设施
│   │   │   ├── llm/             # LLM 抽象（base / factory / openai_compat / ollama）
│   │   │   ├── skills/          # Skill 系统（base / registry / manager / builtin×12）
│   │   │   ├── security/        # dpapi / secret_store / encryption / keyring
│   │   │   ├── scanner/         # 本地扫描
│   │   │   ├── versioning/      # 版本树 + diff
│   │   │   ├── chapter_context.py  # 上下文组装（人物卡 → prompt）
│   │   │   ├── paths.py         # **路径解析统一入口**（开发态/打包态）
│   │   │   ├── watchdog.py      # 父进程看门狗（桌面端崩了后端自己退）
│   │   │   └── config.py
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── schemas/             # Pydantic
│   │   ├── services/            # 业务逻辑
│   │   └── db.py
│   ├── tests/                   # pytest（38+ 文件）
│   ├── book_soul.spec           # PyInstaller 打包配置
│   ├── run_server.py            # 打包入口（绝对 import）
│   └── pyproject.toml
├── config/
│   ├── llm.yaml                 # provider 配置 + 场景路由 + 模型规格
│   ├── app.yaml                 # 用户级默认配置
│   ├── prompts/                 # 8 个提示词 YAML
│   ├── genres/                  # 题材常识（修仙/都市/悬疑/言情）
│   ├── wordbanks/               # 题材词库
│   ├── skills/                  # 用户自定义 skill
│   └── skill_template/          # skill 脚手架
├── scripts/                     # dev / build_standalone / build_sidecar / 快捷方式脚本
├── dist/Book Soul/              # 独立版产物（便携目录，gitignore）
├── data/                        # 运行时（不入 git）
├── docs/                        # DESIGN / PROJECT_STRUCTURE / START_GUIDE / USER_GUIDE
│                                #   / TROUBLESHOOTING / ARCHITECTURE / API / SKILLS
│                                #   + screenshots/（真机截图）
└── .github/workflows/           # ci.yml / release.yml
```

**铁律**：
- 业务逻辑在 `services/`，API 路由只做依赖注入 + 错误映射
- DB 操作走 `models/`，service 不写原生 SQL
- 文件 IO 集中在 service 层
- LLM 抽象在 `core/llm/`，业务不直接 import httpx / 任何 LLM SDK
- **路径解析统一走 `core/paths.py`**，禁止再写 `_find_repo_root()`（历史上散落 8 处，
  且打包态全部失效）
- **一级导航只有 4 项**：写作 / 开新书 / 素材库 / 设置。人物卡、大纲、版本
  是"当前章节的上下文"，不是独立页面 —— 一律放写作页右栏面板（详见 §2.1）

### 2.1 前端 UI 架构（2026-10 重设计后）

```
AppShell（52px 顶栏 + 56px 图标栏）
├── 顶栏 = 全局上下文：作品切换器（全局唯一）+ 面包屑 + 模型状态灯
├── /          写作      三栏：章节树 244px | 纸感编辑区 | 上下文面板 332px
├── /new       开新书    三步向导：种子 → 剧情 → 大纲与人物
├── /library   素材库    三 Tab：作品 / 灵感 / 导入
└── /settings  设置      四分区：LLM 与密钥 / 数据与备份 / AI 增强 / 外观
```

**写作页右栏 5 个 Tab**：生成 / 重写 / 人物 / 大纲 / 版本
—— 全部围绕"当前章节"展开。

**硬约定**：

- **当前作品是全局唯一状态** → `stores/workspace-store.ts`（持久化到 localStorage）。
  禁止在任何页面里再放第二个"作品下拉"（历史上重复了 3 处，切换页面就丢）。
- **编辑区固定浅色纸面**（`.novel-paper`，`#faf8f3`），不随主题切换 ——
  长时间写作不刺眼。跟随主题用 `html.paper-follow-theme` 切换。
- **落库内容取编辑器全文**，不能取流式累积量（生成是追加、重写是替换选区，
  累积量都不是完整正文，直接存会抹掉章节原有内容）→ `pickSavedContent()`。
- 页面文件 ≤ 500 行；右栏每个 Tab 一个文件（`pages/Writing/tabs/`）。

### 2.2 用户可见文档必须跟 UI 同步（2026-10-30 新增）

**改了一级导航 / 页面结构 / 操作路径，就必须同步重写用户能读到的文档。**

| 文档 | 覆盖内容 | 漏了会怎样 |
|---|---|---|
| `README.md` | 快速启动 + 项目结构 + 界面结构表 | 新人按旧路径找不到功能 |
| `docs/DESIGN.md` | 信息架构 + 视觉规范（改 UI 前必读） | 改了配色/尺寸没人知道，界面逐渐跑偏 |
| `docs/USER_GUIDE.md` | 各页面怎么用 | 用户照着找不到按钮 |
| `docs/START_GUIDE.md` | 启动方式 + 人工验证清单 | 验证步骤对不上界面，误判为 bug |
| `docs/TROUBLESHOOTING.md` | 排障 + 应急处理 | 出问题只能来问人 |
| `docs/PROJECT_STRUCTURE.md` | 目录职责 + 数据流 + 修改指引 | 改错文件 / 漏掉联动改动 |
| `docs/ARCHITECTURE.md` | 架构 + 数据模型 | 设计与代码分叉 |

**真实事故（2026-10-30）**：2026-10 UI 重设计把一级导航从 6 项砍到 4 项
（灵感园 / 创作 / 质检 / 仓库 / Skills / 设置 → 写作 / 开新书 / 素材库 / 设置），
但 `README.md` 和 `USER_GUIDE.md` 整整几周都在描述**已经不存在的页面**。
用户按文档点「左侧导航'灵感园'」根本找不到 —— 文档比代码更落后，反而误导人。

**规则**：

- 一级导航、页面拆分、关键按钮文案、路由路径 —— 任何一项变了，
  上面 5 个文档里对应的段落**同一个 commit 内**改掉。
- 文档里出现的数字（模块数 / 测试用例数 / 页面数）要**实测**再写，
  别抄上一版（README 曾写"487 个测试"，实际已是 802）。
- 文档里引用的界面文案要**从源码里抄**，别凭印象写。
  例：按钮真叫「生成 3 个剧情」还是「生成 3 个剧情 →」，看 `pages/NewBook/index.tsx`。

---

## 3. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `character_service.py` |
| Python 类 | PascalCase | `CharacterService` |
| Python 函数/变量 | snake_case | `get_active_characters` |
| Python 常量 | UPPER_SNAKE_CASE | `MAX_OUTPUT_TOKENS` |
| 私有成员 | 下划线前缀 | `_cache` |
| TypeScript 文件 | kebab-case | `model-warning.tsx` |
| React 组件 | PascalCase | `ModelWarningBanner` |
| TypeScript 函数/变量 | camelCase | `checkModel` |
| 配置文件 | snake_case | `llm.yaml` |
| 数据库表 | 复数 snake_case | `characters` |

---

## 4. LLM 调用规范（新增，2026-10）

这是本项目最容易出错、代价最大的地方。**逐条强制**。

### 4.1 流式必须用 `client.stream()`

```python
# ✅ 正确
async with self._client.stream("POST", url, json=payload, timeout=stream_timeout) as resp:
    async for chunk in iter_sse_chunks(resp):
        yield extract_delta_text(chunk)

# ❌ 错误：httpx 会 await response.aread() 读完整个 body 才返回
#         → 后端等模型生成完才推给前端 → "流式跟阻塞一样"
resp = await self._client.post(url, json=payload)
```

> **这是 2026-10 修复的真实 bug**。`server/tests/test_llm_streaming_contract.py`
> 有契约测试锁住行为，改回 `client.post()` 立刻测试变红。

### 4.2 超时必须分流出式/非流式

| 场景 | 配置项 | 含义 |
|---|---|---|
| 非流式 | `timeout_seconds` | 整个响应的总等待上限 |
| 流式 | `stream_read_timeout` | 两个 chunk 之间的最大间隔 |
| 流式 | `stream_total_timeout` | 整条流的总时长上限（防挂死） |

推理模型思考时间可能 > 30s，**不能用 `timeout_seconds` 卡流式**。

### 4.3 必须显式传 `max_tokens`

不传就依赖上游 API 默认值（常见 1024/2048），长章节会被**静默截断**。
`core/llm/openai_compat.py` 会按 `config/llm.yaml` 的 `model_specs.*.max_output_tokens`
自动补，但**业务层显式传值优先**。

### 4.4 业务层禁止直接碰 httpx / SDK

只能走 `core/llm/` 的统一入口。目的是让"换 provider"永远只是一行 YAML 改动。

### 4.5 Provider 健康检查

`core/llm/factory.py` 的 `check_provider_health()` / `check_all_providers_health()`。
启动时后台预检（不阻塞），`GET /llm/health` 供设置页展示。
探活**必须带 API Key**（`/models` 端点需鉴权），否则无法区分"服务挂了"和"key 错了"。

### 4.6 探测超时与缓存（2026-10-24 新增）

健康探测要打**外部网络**，动辄 10 秒。前端顶栏模型灯在启动时就会调
`GET /llm/health` —— 不处理的话，用户盯着一个转圈的灯干等。

| 铁律 | 位置 | 说明 |
|---|---|---|
| `connect_timeout ≤ probe_timeout` | `core/llm/factory.py` | 之前 `min(10.0, timeout)` > `probe_timeout=5`，"网络不通"的 provider 在**连接阶段**就拖满 10 秒（实测 9.8s）。现在 `min(3.0, probe_timeout)` |
| 探测结果必须走 `core/llm/cache.py` | `api/llm.py` + `main.py` | TTL 缓存（健康 60s / 模型 300s）+ stale-while-revalidate，过期时先返回旧值再后台刷新 —— 前端永远不等网络 |
| 预检与 `/llm/health` 必须**共享同一个探测任务** | `core/llm/cache.py::_probe_shared` | 直调 `check_all_providers_health()` 会各打一轮网络，前端启动那一下仍要白等一整轮（实测 2.7s）。**启动预检也要走 `llm_cache.get_health()`** |
| 改 key / provider 后必须作废缓存 | `services/settings_service.py` | `set_api_key` / `delete_api_key` 清该 provider 的模型清单 + 全局健康状态；`update()`（换 provider/model）清全部。不作废的话用户刚换好 key，顶栏还显示着换之前的"Key 无效" |
| 用户主动要新数据时必须能绕过缓存 | `GET /llm/models?refresh=1` | 设置页「刷新列表」按钮用。前端 `llmApi.listModels(provider, refresh)` |

> 契约测试：`server/tests/test_llm_cache.py`（含"预检与 /llm/health 只探测一次"）。
> 改坏了这层，`/llm/health` 会立刻退回 10 秒。

### 4.7 流式端点的三条铁律（2026-10-24 新增，2026-10-29 修订第三条）

用户实测报过三个流式问题，全部归到这三条：

| 铁律 | 说明 | 位置 |
|---|---|---|
| **思考内容不能被丢弃** | 推理模型先吐 `<think>...</think>` 再吐正文，思考可能好几秒。旧写法 `if "<think>" in delta: continue` 把这段**全丢了** → 前端一个字都收不到 → 用户看到"卡住不动"。现在用 `core/llm/streaming.py::ThinkSplitter` 拆成两路，思考内容作为 `thinking` 事件转发 | `core/llm/streaming.py` |
| **流式容器必须能滚动** | 内容区写 `overflow-hidden` + 固定高 → 文字流到边界就被裁掉，后面的字渲染了但**看不见** → 用户看到"生成到一半不动了"，结束时又"一口气全出来"。必须 `max-h-* overflow-y-auto`，并**自动滚到底部** | 前端各流式面板 |
| **并行的 N 个版本：内容实时透传 + 里程碑保序** | 3 个版本并行调用，谁先回是随机的。**内容事件**（thinking / delta）按到达顺序**实时**透传，各版本各显示各的；**里程碑事件**（`version_done` 这类"这个版本好了"）按下标保序，保留出场顺序的观感。用 `merge_queue_events_milestone_ordered`（**生产者仍并行**，只改里程碑顺序，总耗时不变） | `core/queue_merge.py` |

> ⚠️ **不要用"严格保序"（`merge_queue_events_ordered`）** —— 2026-10-25 实测踩过：
> 严格保序的实现是「队列 1 消费完才消费队列 2」，后面版本的内容事件全憋在队列里，
> 等前一个版本彻底结束才**同一毫秒**涌出 —— 用户反馈的原话是
> "生成的时候像是先生成但不输出，阻塞到一整个生成完毕才一口气很快地流式输出"。
> **"一口气"的直接成因就是这个**，不是模型慢，也不是前端缓冲。
> → 拆成两件事：内容永远实时，里程碑才排序。

> ⚠️ **失败版本也要参与保序**（2026-10-29 复核补）——
> 失败的版本发的是 `error` 事件，**不会**发 `version_done`。
> 如果保序指针只认 `version_done`，版本 1 失败时指针就卡住，
> 版本 2/3 的完成事件会被压到**整条流结束**才吐 →
> 用户看到"另外两张卡明明写完了却一直转圈"。
> → `merge_queue_events_milestone_ordered` 的 `terminal_events`
> 默认含 `error`：到达终态（成功或失败）都让指针前进。
> 失败本身仍照常透传给前端（前端 `detectStreamFailure` 负责标记那张卡）。

> 契约测试：`server/tests/test_think_splitter.py` + `test_queue_merge.py` +
> `test_queue_merge_milestone.py`（含"失败版本不阻塞后续里程碑"）+
> `test_plot_generation.py`（顺序 / thinking 事件）。
>
> **性能实测结论（2026-10-24，用本地 mock SSE provider 测）**：
> 代码侧每个 token 只增加 **0.5ms**（实测 40 个 delta，间隔 50.6ms vs mock 的 50ms），
> 整条流的总开销 ~100ms。**流式链路不是瓶颈 —— 慢在模型。**
> 所以别再去优化"转发"环节，要优化的是：模型选型、输出长度、思考时长。
> 埋点：`plot version N: first delta after Xs` / `N deltas, Xs total`（server.log）。

### 4.8 并行 LLM 调用 + 单 Session 写库（2026-10-24 新增）

**并行的是 LLM 调用，串行的是写库。** 这条是 2026-10-24 实测踩出来的。

`AsyncSession` **不是并发安全的**：两个协程同时 `flush()/commit()` 会抛
`InvalidRequestError: Session is already flushing`。

| 场景 | 正确写法 | 位置 |
|---|---|---|
| N 个 LLM 调用并行 | `asyncio.gather(...)` | `services/character_generator.py::generate_from_outline` |
| N 个结果写同一个 session | **for 循环串行**（非流式路径）／**`asyncio.Lock`**（流式路径） | 同上，`stream_generate_from_outline` 里用 `db_lock` |

> 真实事故：人物卡流式生成时 4 张卡的**入库也是并行的** → 3 张抛
> `Session is already flushing` → 用户看到的"已生成 4 个人物卡"是假的。
> 非流式路径一直是对的（先 gather 再串行入库），只有流式路径漏了。
>
> **推广规则**：任何"并行拿结果 → 落库"的代码，写库那一段必须有锁或 for 循环。
> 并行只留给 LLM 调用这种纯网络等待。
>
> 契约测试：`server/tests/test_character_generator.py::test_stream_generate_saves_all_cards_when_generated_concurrently`
> （用 `asyncio.Barrier` 让所有卡同时进入入库阶段，确定性复现竞态）。

### 4.9 同一帧里不要读刚 set 的 state（2026-10-24 新增）

`setState` 是异步的 —— **同一帧里读到的还是旧值**。

```python
# ❌ 前端同理：React 的 setState 也是异步的
onChoose={(idx) => {
  setChosenPlotIdx(idx);
  void startOutlineStream();   // ← 这里读到的 chosenPlotIdx 还是 null / 上一次的值
}}
```

真实事故：点剧情卡本该"选中并生成大纲"，结果第一次点读到 `null` 直接 return
（点了没反应），第二次点才拿**上一张卡**去生成大纲（选 B 生成 A）。

**修法**：需要用刚设的值时，**显式传参**，不要在回调里回头读 state。

```tsx
onChoose={(idx) => { setChosenPlotIdx(idx); }}        // 只管"选中"
onClick={() => void startOutlineStream(chosenPlotIdx)} // 生成时显式传索引
```

> 这条对 Python 同样适用：`await` 之后再读共享的可变状态，时序一样会骗你。

### 4.10 流式失败有两类，前端必须都认（2026-10-24 新增）

NDJSON 流有两种失败长得**完全不一样**，漏掉任何一类，界面都会**永远转圈**：

| 来源 | 事件形状 | 谁产出 |
|---|---|---|
| **transport** | `{ "error": "422 Unprocessable Content" }` | 前端 `readNdjsonStream`（HTTP 非 2xx / 无 body / NDJSON 解析失败） |
| **server** | `{ "event": "error", "message": "..." }` | 后端流内错误帧（`server/src/api/_stream_helpers.py`） |

**只判断 `event === "error"` 的后果**：HTTP 422/500 时 generator 正常 `return`，
`for await` 正常退出，**没有任何分支命中** → 不弹错、不回退 → UI 卡在
"生成中…"无限等待。真实事故：2026-10-24 真机走查，大纲接口 422，
界面停在"流式生成中 …"什么都不发生。

**铁律**：所有 `readNdjsonStream` 的消费方，第一件事就是调
`detectStreamFailure(ev)`（`apps/desktop/src/api/streams.ts`），不要自己判 `event`。

```tsx
const failure = detectStreamFailure(ev);
if (failure) {
  toast.error("大纲生成失败", { description: failure.message });
  setStep("plot");   // 必须回退，不能停在半路
  return;
}
```

> 写作页 `use-chapter-stream.ts` 早就在用 `isStreamError`，
> 但**开新书页三个流循环（剧情 / 大纲 / 人物卡）都没用** —— 同一种错误，
> 一个页面处理了，另一个页面没处理。**新增流消费方时照抄写作页，不要照抄邻居。**

契约测试：`apps/desktop/src/api/__tests__/streams.test.ts`
（`detectStreamFailure` 覆盖 transport / server / 缺 message / 正常事件四类）。

### 4.11 正文排版与字数口径（2026-10-30 新增，**用户实测的重大质量事故**）

用户实测反馈：「生成的小说文本多出大量空余字符，没有分段分行，不同人物的对话无法区分」
+「目标字数 3600，程序提示 5338 字，实际 3309 字」。

**取证**（用户真实库 `《骨仙传》第 1 章`）：`len(content)=5338`，其中 **2024 个字符是
换行**（1012 组 `\n\n`），真实正文只有 **3314 字**（Word 统计 3309 是对的）。

#### 铁律一：字数口径 = **非空白字符数**（含中文标点）

```python
# server/src/core/prose_format.py::count_prose_words
return sum(1 for c in text if not c.isspace())
```

❌ **禁止用 `len(content)`** —— 它把换行符和空格全算进去，界面字数虚高，
和 Word 导出对不上（这就是"提示 5338 / 实际 3309"的成因）。
新口径与 Word 的「字数」、网文平台（起点/番茄）一致。

⚠️ 前端 `lib/prose-text.ts::countProseWords` 必须**与后端完全一致**
（注意 JS 的 `\s` **不匹配全角空格 U+3000**，要单独覆盖）。

#### 铁律二：编辑器追加文本必须插进**最后一个段落内部**

```tsx
// ❌ 错：在文档末尾 insertText → ProseMirror 会「新建一个段落」
const docSize = view.state.doc.content.size;
tr.insertText(text, docSize);

// ✅ 对：最后一个文本块的内容末尾位置
const last = doc.content.lastChild;
const pos = doc.content.size - last.nodeSize + 1 + last.content.size;
```

**为什么这是重大事故**：流式追加是每 16ms 一次 flush，每次 flush 新建一个段落 →
Tiptap 的 `getText()` 又用 `"\n\n"` 拼块 → 正文被切成 **1012 个 1-7 字的假段落**。
假换行把字数撑到 5338，重新载入时又因为纯文本被当 HTML 解析成一个大段落，
界面变成"一行行挤在一起、字间有空格"。

#### 铁律三：正文排版必须过 `ProseFormatter`

`server/src/core/prose_format.py::ProseFormatter`（**增量**，边流边整理）：

| 规则 | 为什么 |
|---|---|
| 去掉**汉字之间**的空格 | 模型常见毛病"山 门 前 的"→ 用户看到的"空余字符" |
| 保留英文单词之间的空格 | 英文句子不能被粘在一起 |
| 模型给的 `\n` → 段落分隔 | |
| **兜底断段**（段落 ≥30 字遇句末标点） | 实测 MiniMax-M3.1-Flash **整章零换行**，只靠 prompt 靠不住 |
| 对白 `”` / `」` 收尾后另起一段 | 多人对话能分辨谁在说话 |
| **连续对白强制断段** | `“甲？”“乙。”` 直接拆成两段 —— 见下方铁律五 |

生成与重写两条链路都要接：`chapter_generator.py` / `chapter_rewriter.py`。

#### 铁律四：**连续对白**必须拆段，但**引用**不能拆

用户实测的三个痛点之一是「不同人物的对话无法区分」。判据必须精确，否则会拆坏句子：

| 文本 | 拆不拆 | 原因 |
|---|---|---|
| `“沈砚？”“沈家村，沈砚。”` | **拆** | 闭引号前是句末标点 `？` → 上一句说完了，换人了 |
| `将“沈”“砚”二字划去` | **不拆** | 闭引号前是 `沈` → 引号内没有句末标点，这是**引用词语** |

实现（`core/prose_format.py::_starts_new_dialogue`）：三个条件同时成立才断 ——
① 当前字符是引号开头 `“ ‘ 「`；② 上一个非空白字符是引号收尾 `” ’ 」`；
③ **收尾引号的前一个字符是句末标点** `。 ！ ？`。

⚠️ 条件 ③ 是关键 —— 少了它，`将“沈”“砚”二字` 会被拆成两段，把词组拆断。

已排版好的历史章节做二次修整用
`split_consecutive_dialogue()`（**保留原有段落划分**，只拆对白），
配套 CLI：`scripts/repair_chapter_paragraphs.py --split-dialogue`。

#### 铁律五：正文是**纯文本**，不是 HTML

后端存的是纯文本，段落分隔符是 `\n\n`。前端 `setContent` 必须先把纯文本**转成
多个段落**再交给 Tiptap，否则纯文本会被当 HTML 解析成一个大段落，
`\n` 渲染成空格 → 整章挤成一行。

#### 契约测试

- `server/tests/test_prose_format.py` —— 排版器 30 个用例（含连续对白 6 个）
- `server/tests/test_chapter_generation.py` —— 生成链路确实过了排版器
- `apps/desktop/src/lib/__tests__/prose-text.test.ts` —— 前端口径与后端一致
- 历史数据修复：`scripts/repair_chapter_paragraphs.py`
  - 默认模式：假段落 → 重新断段（还原被流式追加切碎的正文）
  - `--split-dialogue`：保留段落划分，只拆连续对白
  - 两种模式都**新建版本**，原版本留在历史里可回滚


---

## 5. 桌面化与打包规范（新增，2026-10）

### 5.1 目标形态

**双击即用的独立桌面应用**。用户不需要装 Python / Node / Rust，不需要开终端，
不需要手动起后端。数据默认存在应用目录里（便携模式），整个文件夹拷走就是完整迁移。

### 5.2 架构约定

| 约定 | 位置 | 说明 |
|---|---|---|
| 随机空闲端口 | `src-tauri/src/sidecar.rs` | 不死绑 8765，避免多开冲突 / 旧进程残留 |
| 数据目录（便携） | `src-tauri/src/sidecar.rs` | release：exe 同级 `data/`；dev：`<repo>/data/dev` |
| sidecar 定位 | `src-tauri/src/sidecar.rs` | Tauri 会**剥掉 target-triple 后缀**，exe 同级目录优先 |
| 就绪握手 | `backend_ready` command | 前端先等后端 ready 再拉数据，避免首屏 503 |
| 端口下发 | `get_backend_url` command | 前端**不得硬编码** `127.0.0.1:8765` |
| 启动失败透传 | `get_backend_error` command | 后端拉不起来时把**真实原因**给前端，不给用户白屏 |
| 桌面端日志 | `src-tauri/src/logging.rs` | release 无控制台 → 写 `data/logs/desktop.log` |
| 流式直连 | `api/streams.ts` | 流式**不经过 Rust**（`invoke` 是一次性调用，做不了流式转发） |
| sidecar | `tauri.conf.json` → `externalBin` | Python 后端由 PyInstaller 打成 exe 随包分发 |
| 打包入口 | `server/run_server.py` | **必须用绝对 import**（`src/main.py` 的相对 import 在 `__main__` 下会失败） |
| 孤儿进程防护 | `core/watchdog.py` | 桌面端传 `--parent-pid`；父进程没了后端自己退出 |
| 打包版 CLI | `src/main.py::run_from_cli` | dev 与打包版**共用**一份 argparse（`run_server.py` 不自己解析参数） |
| 关窗不卡顿 | `src-tauri/src/sidecar.rs` | 杀后端**必须放后台线程**，绝不能跑在窗口关闭事件处理器的 UI 线程上（`taskkill` 要 spawn 子进程，200–500ms → 窗口会僵住半秒） |
| 杀进程不无限等 | `src-tauri/src/sidecar.rs::kill_backend_child` | 轮询 `try_wait`，**2 秒上限**。之前用阻塞的 `child.wait()`，taskkill 一旦失败窗口就永远关不掉 |
| 异常退出兜底 | `src-tauri/src/lib.rs` (`RunEvent::Exit`) | 走异常退出路径时**同步**杀（slot 非空即说明是异常路径），spawn 线程会随 app 退出被杀掉 → 后端成孤儿 |
| 打开数据目录 | `src-tauri/src/lib.rs::open_data_dir` | **不要用 shell 插件的通用 `open`**（权限面太大）。只暴露"打开数据目录"这一个固定动作 |

### 5.3 打包流程

```bash
# 1. 一键出独立版（推荐）—— 产物在 dist\Book Soul\，整个文件夹拷走就能用
powershell -ExecutionPolicy Bypass -File scripts/build_standalone.ps1

# 2. 手动分步
powershell -ExecutionPolicy Bypass -File scripts/build_sidecar.ps1   # PyInstaller 打后端
cd apps/desktop && pnpm tauri build                                # 前端 + Rust + 打包
```

**打包前必须自检**：
- `config/` 目录必须作为数据打进包（提示词/题材/词库是运行时依赖）
- `.env` **绝不能**打进包
- `server/run_server.py` 是唯一入口

> ⚠️ **改完前端必须重新打包，否则用户看到的还是旧 UI**
>
> Tauri 打包版的前端资源是**嵌进 exe 二进制**的（不是运行时读目录）。
> 改完 React 源码 → 跑 `pnpm dev` 或 `vite build` **都不会**更新
> `dist\Book Soul\Book Soul.exe` —— 启动器跑的还是那个旧 exe。
>
> 改前端 → 想让用户看到效果，必须重新走一遍打包：
> ```powershell
> powershell -ExecutionPolicy Bypass -File scripts\build_standalone.ps1
> ```
>
> 排查"我改了 UI 但软件里没变"时，**先看 exe 时间戳**：
> `dist\Book Soul\Book Soul.exe` 的 `LastWriteTime` 必须晚于
> `apps\desktop\src` 里最新的源码时间，否则就是没重新打包。
> （`build_standalone.ps1` 末尾自带新鲜度自检，会打这条警告。）

### 5.4 打包态路径

打包后没有 `pyproject.toml`，向上找目录必然失败。
**所有路径必须走 `core/paths.py`**，它处理 `sys._MEIPASS`（PyInstaller 解包目录）。

### 5.5 启动器

| 脚本 | 用途 |
|---|---|
| `scripts/build_standalone.ps1` | 一键构建独立版到 `dist/Book Soul/` |
| `scripts/launcher.vbs` | 零控制台入口（被快捷方式调用） |
| `scripts/launcher_hidden.ps1` | 优先跑独立版 exe；没有则退回开发模式 |
| `scripts/dev.ps1` | 开发模式（可见控制台，看日志） |
| `scripts/install_shortcut.ps1` | 建桌面/开始菜单快捷方式，**优先指向独立版 exe** |

> 启动器**不硬编码端口**。端口由 Rust 侧分配随机空闲端口。

---

## 6. 安全规范

- ✅ 所有 SQL 用 SQLAlchemy ORM（自动参数化）
- ✅ 所有文件操作检查路径（防越界，`Path.resolve()` 后必须以 `data_dir` 开头）
- ✅ 所有网络请求加超时
- ✅ 所有用户输入校验（Pydantic schema）
- ✅ API Key 存储优先级：**环境变量 > DPAPI 加密文件 > 系统 Keyring**
  - DPAPI（Windows Data Protection API）：用当前 Windows 账户凭据派生密钥，
    文件可随应用目录迁移，明文永不落盘，**零第三方依赖**（ctypes 调 crypt32.dll）
  - 打包版默认走 DPAPI；开发期用环境变量最方便
  - ❌ **禁止**明文 `.env` 出现在分发目录
- ✅ 章节字数硬限 1k-8k（**唯一来源：`config/llm.yaml` 的 `chapter_limits`**）
- ✅ context_window 必须 ≥ 32k 才能生成章节
- ✅ 加密默认关闭，开启后警告用户备份风险

### 6.1 作品名唯一（2026-10-30 新增，数据完整性铁律）

**素材库里同一时间只能有一本同名作品。** 名字去首尾空白后**精确匹配**（不做大小写折叠）。

| 场景 | 必须的行为 | 位置 |
|---|---|---|
| 用户主动填名撞车 | 抛 `NovelNameConflictError` → HTTP **409**，前端提示"换个名字" | `services/novel_service.py` |
| 程序自动命名撞车 | **自动加序号**（`X` → `X 2` → `X 3`），静默避让 | `novel_service.unique_name()` |
| 导入本地小说撞名 | 同上，自动加序号 | `core/scanner/novel_importer.py` |

**前后端规则必须完全一致** —— 前端的 `lib/novel-name.ts` 和后端的
`novel_service.name_taken()` 是同一套规则的两份实现，改一处必须改另一处，
否则会出现"前端说没重名、后端 409"。

> ⚠️ **禁止按名字 upsert 作品**（2026-10-30 修掉的数据丢失 bug）。
> 旧 `outline_generator._upsert_novel()` 是「`Novel.name == name` 就复用那本」，
> 结果：程序自动命名撞上已有作品 → 复用旧书 → 同 type 大纲被删掉重建、
> 人物卡也写进旧书的 `novel_id` → **新书存不进素材库，旧书数据被静默覆盖**。
>
> 现在**靠 id 而不是靠名字**区分"重生成同一本"和"新建一本"：
> `outline_generator._resolve_novel()` —— 传 `novel_id` → 复用该本（名字没被占用才改名）；
> 不传 → **新建一本**且名字保证唯一。
> 契约测试：`server/tests/test_outline_generator.py::test_generate_same_name_creates_new_novel`
> / `test_generate_reuses_novel_by_id`。

---

## 7. 测试规范

### 7.1 覆盖要求

- 业务逻辑必须有测试
- 边界条件（空、None、超长）必须有测试
- 错误路径（异常抛出）必须有测试
- **前端关键逻辑也要测**（流式解析、状态机跳转、diff 渲染）

### 7.2 流式契约测试（强制）

所有流式端点必须有"**第一个 chunk 在数据源结束前就被 yield**"的断言。
用假 SSE 源（带间隔的 async generator）实现。

> 没有这条测试，假流式 bug 一定会复发。

### 7.3 测试隔离注意

`conftest.py` 的 `temp_db` fixture 会把 `src.*` 从 `sys.modules` 删除再重新导入。
**异常类、自定义异常必须在测试文件顶层 import**，不能在函数体 import ——
否则 `pytest.raises(X)` 拿到的是新类，client 抛出的是旧类，永远不匹配。

### 7.4 覆盖率

`pytest --cov=src --cov-report=term-missing`，目标 **≥ 70%**（核心模块 ≥ 80%）。

---

## 8. 代码规范

### 8.1 代码量

- **单文件 ≤ 500 行**（超了按职责拆分）
  - 为什么要文件级而不是函数级：AI 定位问题永远从文件开始；函数级行数限制会逼 AI
    把连贯逻辑切成互相传参的碎片函数，反而更难维护
- **不再限制单函数行数**（原"≤ 200 行"已废止）
- **每个函数/类必须有 docstring**（说明它做什么、为什么这么做）

### 8.2 严格禁止

- ❌ 不用 LangChain / LlamaIndex
- ❌ 不用 Flask / Django
- ❌ 不用 Electron
- ❌ 前端代码不硬编码任何 API Key / 后端地址
- ❌ `.env` / `.env.local` 不提交 git
- ❌ 不用 print 调试（用 loguru）
- ❌ **流式调用用 `client.post()`**（见 §4.1）
- ❌ **业务层直接 import httpx / LLM SDK**（见 §4.4）
- ❌ **再写 `_find_repo_root()`**（见 §2）
- ❌ SQL 用字符串拼接（必须用 ORM）
- ❌ 不引用未确认的库/函数（先查官方文档确认存在）
- ❌ 不跳过测试写新功能
- ❌ 不用 Tailwind 之外的 CSS 方案（除非组件库强依赖）
- ❌ 不引入非必要依赖

### 8.3 提示词管理

所有 prompt 必须在 `config/prompts/*.yaml`：

```yaml
version: 1  # 必带
changelog:  # 改动时记录
  - "v1: 初始版本"
prompt: |
  ...
```

**绝对不要**把 prompt 散落在 Python 代码里。
加载用 `lru_cache` + `str.format()`；模板占位符写错要立刻报明确错误。

### 8.4 日志

- 一律用 `loguru`，不用 `print`
- `setup_logging()` 会 `logger.remove()` 掉默认 handler —— **不要重复添加 sink**
  （否则每条日志输出两遍，打包成 sidecar 后尤其明显）

### 8.5 PowerShell 脚本必须带 UTF-8 BOM

Windows 上的 PowerShell **5.1**（系统自带那个）读 `.ps1` 文件时：
- 有 BOM → 按 UTF-8 解码 ✅
- 无 BOM → **按系统 ANSI 代码页解码**（中文机器上是 GBK）→ 中文全乱码，
  更糟的是乱码后的字节序列可能提前终止 here-string（`@"..."@`），
  导致脚本"看起来跑完了"但内容写空。

**铁律**：`scripts\*.ps1` 一律存成 **UTF-8 with BOM**。
新增或修改 `.ps1` 后，提交前用这个命令自检：

```powershell
Get-ChildItem scripts\*.ps1 | ForEach-Object {
  $b = [IO.File]::ReadAllBytes($_.FullName)
  "{0}: BOM={1}" -f $_.Name, ($b[0] -eq 0xEF)
}
```

> 这不是洁癖：2026-10 就是因为 `build_standalone.ps1` 没带 BOM，
> README.txt 被写成了 0 字节，而且中文全是乱码。
> 同理，**含中文的 `.ps1` 一定要带 BOM**；纯 ASCII 脚本建议也带，避免以后加中文踩坑。
>
> ⚠️ **2026-10-24 又踩了一次，而且失败模式更隐蔽**：临时测量脚本用无 BOM + 中文注释，
> GBK 解码后字节错位，**注释行把下一行整行吞掉了** ——
> 那行 `$x = Measure-Get "..."` 根本没执行，变量保持 `$null`，
> 脚本却"跑得好好的"，只是那一行的测量值莫名其妙是空。
> 症状：同一函数的前后两次调用，一次有值一次为空。
> **判据**：只要 `.ps1` 里有中文，就当它一定会被 GBK 误解码；
> 临时脚本最省事的做法是**只写 ASCII**（注释也用英文）。

---

## 9. 性能预算（新增，2026-10）

| 指标 | 目标 | 怎么测 |
|---|---|---|
| 首字延迟 | 发起生成 → 第一个字符 **≤ 3s** | 计时断言 |
| 启动时间 | 双击 exe → UI 可交互 **≤ 5s** | 打包后测 |
| 章节生成 prompt | 只带**本章出场人物**的人物卡 | `select_relevant_characters` |
| LLM 连接 | 进程级复用（`get_cached_llm_client`） | 不要再每次新建 client |

**上下文瘦身**：`core/chapter_context.py` 的 `select_relevant_characters()`
只保留「名字出现在本章上下文」+「主角/主角团」的角色卡。一个都没匹配上时
**退回全部**（宁可多给，不可少给）。

---

## 10. 提交流程

```bash
# 1. 跑质量门禁
pre-commit run --all-files
pytest
# 必须全过

# 2. 提交（分批，语义清晰）
git add <明确的文件路径>   # 不用 git add .
git commit -m "Phase X 模块 Y: <描述>"

# 3. 推送（**必须用户明确要求才 push**）
git push origin main
```

---

## 11. 模块开发流程

每个模块按以下顺序：

1. **测试先行**（如适用）：先写 `test_xxx.py` 测试用例
2. **实现代码**：`src/xxx.py` 实现
3. **本地验证**：`pytest` + `ruff check` + `ruff format --check`
4. **commit**：清晰消息（用户确认后）
5. **用户验证**：给用户"用户验证清单"

---

## 12. 沟通原则

- 简洁直接，不啰嗦
- 不确定就问，不要瞎猜
- 引用代码用 `file_path:line` 格式
- 完成后给"用户验证清单"和 commit 消息建议

---

## 参考资料

- 核心设计决策 + 模块完成状态：`PROJECT_PLAN.md`（历史快照）
- 安全策略：`SECURITY.md`
- 界面设计规范（改 UI 前必读）：`docs/DESIGN.md`
- 项目结构 + 数据流：`docs/PROJECT_STRUCTURE.md`
- 排障与应急：`docs/TROUBLESHOOTING.md`
- 架构设计：`docs/ARCHITECTURE.md`
- 开发行为约束：[DEVELOPMENT_CONSTRAINTS.md](./DEVELOPMENT_CONSTRAINTS.md)（沟通、流程、决策）
