# AGENTS.md - Book Soul 项目规范

<!--
修改记录
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
│   │   ├── pages/               # 6 个主页面
│   │   ├── stores/              # Zustand 状态
│   │   ├── lib/  config/  types/
│   ├── src-tauri/
│   │   ├── src/lib.rs           # 桌面壳：拉起后端 / 端口 / 数据目录
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
│   │   │   ├── workflow/        # 状态机
│   │   │   ├── memory/          # 项目/会话/RAG 记忆
│   │   │   ├── quality/         # 质检 prompt
│   │   │   ├── chapter_context.py  # 上下文组装（人物卡 → prompt）
│   │   │   ├── paths.py         # **路径解析统一入口**（开发态/打包态）
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
│   ├── prompts/                 # 12 个提示词 YAML
│   ├── genres/                  # 题材常识（修仙/都市/悬疑/言情）
│   ├── wordbanks/               # 题材词库
│   ├── skills/                  # 用户自定义 skill
│   └── skill_template/          # skill 脚手架
├── scripts/                     # dev.ps1 / build_sidecar.ps1 / 快捷方式脚本
├── data/                        # 运行时（不入 git）
├── docs/                        # ARCHITECTURE / API / USER_GUIDE / SKILLS
└── .github/workflows/           # ci.yml / release.yml
```

**铁律**：
- 业务逻辑在 `services/`，API 路由只做依赖注入 + 错误映射
- DB 操作走 `models/`，service 不写原生 SQL
- 文件 IO 集中在 service 层
- LLM 抽象在 `core/llm/`，业务不直接 import httpx / 任何 LLM SDK
- **路径解析统一走 `core/paths.py`**，禁止再写 `_find_repo_root()`（历史上散落 8 处，
  且打包态全部失效）

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

---

## 5. 桌面化与打包规范（新增，2026-10）

### 5.1 目标形态

**双击即用的独立桌面应用**。用户不需要装 Python / Node / Rust，不需要开终端，
不需要手动起后端。数据默认存在应用目录里（便携模式），整个文件夹拷走就是完整迁移。

### 5.2 架构约定

| 约定 | 位置 | 说明 |
|---|---|---|
| 随机空闲端口 | `src-tauri/src/lib.rs` | 不死绑 8765，避免多开冲突 / 旧进程残留 |
| 数据目录（便携） | `src-tauri/src/lib.rs` | release：exe 同级 `data/`；dev：`<repo>/data/dev` |
| 就绪握手 | `backend_ready` command | 前端先等后端 ready 再拉数据，避免首屏 503 |
| 端口下发 | `get_backend_url` command | 前端**不得硬编码** `127.0.0.1:8765` |
| 流式直连 | `api/streams.ts` | 流式**不经过 Rust**（`invoke` 是一次性调用，做不了流式转发） |
| sidecar | `tauri.conf.json` → `externalBin` | Python 后端由 PyInstaller 打成 exe 随包分发 |
| 打包入口 | `server/run_server.py` | **必须用绝对 import**（`src/main.py` 的相对 import 在 `__main__` 下会失败） |

### 5.3 打包流程

```bash
# 1. 构建 sidecar（自动读 target triple 并放到 Tauri 期望的位置）
powershell -ExecutionPolicy Bypass -File scripts/build_sidecar.ps1

# 2. 完整打包（beforeBuildCommand 会自动跑第 1 步）
cd apps/desktop && pnpm tauri build
```

**打包前必须自检**：
- `config/` 目录必须作为数据打进包（提示词/题材/词库是运行时依赖）
- `.env` **绝不能**打进包
- `server/run_server.py` 是唯一入口

### 5.4 打包态路径

打包后没有 `pyproject.toml`，向上找目录必然失败。
**所有路径必须走 `core/paths.py`**，它处理 `sys._MEIPASS`（PyInstaller 解包目录）。

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

- 完整开发计划：`PROJECT_PLAN.md`
- 用户准备清单：`USER_CHECKLIST.md`
- 安全策略：`SECURITY.md`
- 架构设计：`docs/ARCHITECTURE.md`
- 开发行为约束：[DEVELOPMENT_CONSTRAINTS.md](./DEVELOPMENT_CONSTRAINTS.md)（沟通、流程、决策）
