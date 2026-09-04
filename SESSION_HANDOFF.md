# Book Soul · 工作台交接文档（Session Handoff）

> **创建原因**：用户从 minimax code 切换到 Zcode 继续开发，跨 agent 的对话历史无法保留
> **创建时间**：2026-09-04
> **保持者**：JEE
> **版本**：v1
>
> **使用方式**：
> 1. 切到 Zcode 后，**第一条消息**把 §E 沟通模板贴给新 agent
> 2. agent 会自动读 AGENTS.md / DEVELOPMENT_CONSTRAINTS.md / PROJECT_PLAN.md 这三件套
> 3. 如有需要，再参考本文件的其他章节
>
> **本文件不替代**规范三件套（AGENTS.md / DEVELOPMENT_CONSTRAINTS.md / PROJECT_PLAN.md），只是"暖场"。

---

## A. 项目身份（agent 必读背景）

| 项目 | 值 |
|------|---|
| 名字 | Book Soul |
| 类型 | 小说 AI 写作桌面应用（网文 + 严肃文学） |
| 目标用户 | JEE（网文作者 + 初学开发者，vibe coding 模式） |
| 部署 | Tauri 2 桌面应用 + GitHub 公开仓库 |
| 工作目录 | `C:\Users\JZ\Desktop\Book Soul` |
| 核心特色 | 人物卡驱动一致性 + Skill/Tool 系统 + 双模式 LLM（云端 + 本地 Ollama） |

**规范三件套**（任何 agent 接手前必读）：
1. `AGENTS.md` —— 技术规范（栈、命名、禁止、安全、测试、代码量、提交流程、模块开发流程）
2. `DEVELOPMENT_CONSTRAINTS.md` —— 行为约束（沟通、流程、决策、agent 工作流、错误处理）
3. `PROJECT_PLAN.md` —— 开发计划书（每个 Phase / 模块 / 步骤 / 验证点）

---

## B. 已锁定的关键决策（不要再讨论，直接遵循）

### B.1 技术栈（来自 AGENTS.md）

| 层级 | 选型 |
|------|------|
| 桌面壳 | Tauri 2（❌ Electron） |
| 前端 | React 18 + TypeScript + Vite + Tailwind + shadcn/ui + Tiptap + Zustand |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy 2 + SQLite（aiosqlite） |
| 向量库 | ChromaDB（嵌入式） |
| LLM 抽象 | 自研 ~200 行 Protocol（❌ LangChain / LlamaIndex） |
| 包管理 | uv（Python）+ pnpm（Node） |
| Lint | ruff（❌ flake8 / black） |
| 类型检查 | mypy |
| 测试 | pytest |
| 加密 | cryptography.Fernet（可选，默认关闭） |
| API Key | 系统 Keyring（❌ 不入 .env 不入 git） |

### B.2 业务决策

- **题材优先级**：修仙 → 都市 → 悬疑 → 言情（从左到右依次递减）
- **辅助开发模型上下文**：1M tokens（minimax-M3）
- **章节字数硬限**：1k - 8k
- **LLM 模型警告**：用户配置模型 context_window < 32k 时，UI 弹警告（不能生成章节）
- **加密默认关闭**，开启后 UI 警告用户备份风险
- **数据库操作必须用 ORM**（绝不写原生 SQL，AGENTS.md §安全规范）
- **文件 IO 集中在 service 层**（不在 core/ 散落）
- **所有 prompt 走 YAML**（`config/prompts/*.yaml`），不散落在 Python 代码
- **单函数不超过 200 行**，单模块不超过 300 行（AGENTS.md §模块代码量控制）
- **质量门禁**：pre-commit（ruff + gitleaks）+ pytest，全过才能 commit

### B.3 非目标（明确不做）

- ❌ 用户账号系统 / 主密码 / 密码派生
- ❌ 云端同步 / 多人协作
- ❌ LangChain / LlamaIndex 重型框架
- ❌ Electron
- ❌ 散落文档到用户主目录

---

## C. 进度快照

### C.1 Phase 状态

| Phase | 状态 | 备注 |
|-------|------|------|
| 0：环境与基建 | ✅ 完成 | 模块 0.1-0.10 |
| 1：核心后端服务 | ✅ 完成 | 模块 1.1-1.7（含 1.6 加密 / 1.7 记忆骨架） |
| 2：桌面壳 + 前端骨架 | 🟡 **2.6 进行中** | 2.1-2.5 ✅ |
| 3：灵感园 - 开新书 | ⏸ 未开始 | 计划包含题材选择、词库、灵感词生成 |
| 4-7 | ⏸ 未开始 | 详见 PROJECT_PLAN.md |

### C.2 最近 commit（5 条）

```
aba570e fix: dev.ps1 显式传 env + 启动前杀端口 8765 老 Python
cf6de86 fix: dev.ps1 路径解析回退到简单形式
06533f3 fix: dev.ps1 隔离 dev 数据目录到 data/dev/
1ae9e8e Phase 2 模块 2.5: Zustand 状态管理（3 stores）
8b36d88 Phase 2 模块 2.4: 设置页基础 (LLM/Key/Theme/加密)
```

### C.3 Phase 2.6 范围（即将提交 / 已提交）

**已完成**：
- `config/genres/*.yaml` × 4（dushi / xiuxian / xuanyi / yanqing）
- `config/wordbanks/*.yaml` × 4（同上 4 题材）
- `config/prompts/*.yaml` × 3（outline_complete / outline_freedom / plot_generation）
- `server/src/services/outline_generator.py` + 测试
- `server/src/services/wordbank_service.py` + 测试
- `server/src/services/inspiration_service.py`（增强）+ 测试
- `server/src/api/wordbanks.py` + 配套 schema / API
- `server/src/core/llm/formatting.py`（新增）
- `apps/desktop/src/pages/Inspiration/` 5 组件（GenreSelect / KeywordBoard / OutlineGenerator / PlotGenerator / WordSection）
- `apps/desktop/src/api/wordbanks.ts`（API 客户端）
- 一键启动：`start.bat` + `Start Book Soul.vbs`
- 临时调试脚本：`scripts/_verify_*.py` × 7 + `_dedupe*.py` × 2 + `_check_wordbanks.py`（**注意：临时脚本未清理**）
- `config/llm.yaml`（timeout 等参数微调）
- `apps/desktop/src-tauri/tauri.conf.json` + `lib.rs`（端口/路径相关）
- `server/src/core/llm/factory.py` + `openai_compat.py`（timeout 配置接入）

**未完成 / 下一步**：
- 灵感园 5 组件的端到端验证（可能还没全部跑通）
- Phase 2.6 commit 后的 verification round
- Phase 2.7（如果有）
- Phase 3 启动：题材选择 + 词库系统的 UI 串通

### C.4 当前 branch / 工作树状态

- branch: `main`
- 提交：所有 Phase 2.6 工作已 commit（参见 commit history 最近的 "Phase 2.6 ..." 风格 commit）
- **脏文件**：commit 之后应该干净。如果 `git status` 仍有 M / ??，说明有未完成的工作或新发现的问题

---

## D. 已知问题 / 待处理清单

### D.1 代码层面（从工作树 / commit message 推断）

- `scripts/_verify_*.py` 和 `scripts/_dedupe*.py` 是开发期临时调试脚本，**应该在某个时间点清理**（移到 `tmp/` 或加 `.gitignore` 规则）
- 端口 8765 占用问题在最近 3 个 commit 反复 fix（dev.ps1 路径解析、env 传递、杀老 Python）—— **启动脚本仍是脆弱点**，若新人遇到启动失败优先看 dev.ps1 / start_backend.ps1
- `data/` 目录有 8+ 个 curl-test / chapter-curl / character-curl 等临时测试产物——这些**已被 .gitignore 排除**，无需处理

### D.2 启动 / 环境

- **一键启动**：`start.bat`（或双击 `Start Book Soul.vbs`）会启动后端 + 前端
- **手动启动**：后端 `uv run python -m server` 或 `.\scripts\start_backend.ps1`；前端 `cd apps/desktop && pnpm dev`
- **.env 位置**：项目根 `C:\Users\JZ\Desktop\Book Soul\.env`（**不**在 git 里）
- **venv**：项目根 `.venv/`，由 uv 管理

### D.3 测试覆盖现状

- Phase 1 service 全部有 pytest 覆盖
- Phase 2.6 新增的 `outline_generator` / `wordbank_service` / `plot_generation` 也有对应测试
- **Phase 2.6 commit 后应跑**：`pytest server/tests/` 确认全绿
- **前端暂无自动化测试**（Tauri 项目暂不引入 vitest，留待后续 Phase）

### D.4 数据 / 隐私红线

- `.env` 含真实 API Key（MiMo / minimax / OpenAI / Anthropic）
- `.env` 已在 `.gitignore`，不会进 git
- **任何备份 / 压缩包 / 云同步都不能带 .env**
- LLM 真实密钥已存入系统 Keyring，.env 里的值是 keyring 引用名（具体看 .env 内容判断）

---

## E. 沟通模板（**切到 Zcode 后第一条消息贴这个**）

直接复制粘贴 ↓

---

```
你好，这是 Book Soul 项目的工作台交接，我刚把 agent 从 minimax code 切到你（Zcode）。

**先读这三份规范**（按顺序）：
1. AGENTS.md（技术规范）
2. DEVELOPMENT_CONSTRAINTS.md（行为约束）
3. PROJECT_PLAN.md（开发计划书）

**项目状态**：
- Phase 0-1 完成，Phase 2.1-2.5 完成
- Phase 2.6（灵感园 + 词库 + 题材）刚 commit，工作树应干净
- 最近 commit 应该是 "Phase 2.6: ..." 风格的提交
- 题材优先级：修仙 → 都市 → 悬疑 → 言情
- 技术栈：Tauri 2 + React 18 + FastAPI + SQLAlchemy 2 + 自研 LLM 抽象（不用 LangChain）

**请你**（严格按 DEVELOPMENT_CONSTRAINTS.md §2.2）：
1. 跑 `git log --oneline -10` 和 `git status` 确认状态
2. 简要报：当前进度 / 下一个待办 / 任何阻塞项
3. 询问我下一步要做什么

**提醒**：
- 不要假设你知道之前的对话历史
- 一切以项目文件 + 本消息为准
- 严格按 DEVELOPMENT_CONSTRAINTS.md §3.1 行事：commit / push 前必须等我明确确认
- 临时调试脚本（scripts/_*.py）暂留，不用现在清理

```

---

## F. 我之前讨论过但没记到文件里的事

> ⚠️ 这部分是我尽力从代码 / git / 规范文件**推断**的，不能 100% 准确。
> 如果你（JEE）记得更具体的内容，请直接补充。

### F.1 关于 Phase 2.6 的范围调整

- 从 `config/genres/*.yaml` + `wordbanks/*.yaml` 看，**4 题材都做了词库**（不只是优先级最高的修仙）
- 这可能意味着"题材优先级"是**业务排序**（先做什么），不是"其他题材不做"
- 与 PROJECT_PLAN.md §B.1 的"题材优先级"定义需要核对

### F.2 关于 LLM provider 配置

- `config/llm.yaml` 改了 timeout 相关参数
- `server/src/core/llm/factory.py` + `openai_compat.py` 改了接入方式
- **可能**：用户反馈过"模型生成慢/超时"的问题，新增 timeout 配置

### F.3 关于启动脚本反复修复

- 最近 3 个 commit 全是 fix dev.ps1
- **可能**：用户开发时反复遇到启动失败（端口占用、路径解析、env 传递）
- 建议 Zcode 接手时跑一次 `start.bat` 端到端验证，确认已稳定

### F.4 关于临时调试脚本的来源

- `scripts/_verify_*.py` × 7：开发中用来手动验证 API 行为（每次调 LLM 接口时跑）
- `scripts/_dedupe*.py` × 2：词库去重工具，可能是词库 YAML 整理时用
- `scripts/_check_wordbanks.py`：词库检查
- **建议**：Zcode 接手后某个时间点清理（移到 `tmp/` 或加 `.gitignore`），但**现在不强制**

---

## G. 切到 Zcode 后的第一步清单

- [ ] 读 AGENTS.md（技术规范）
- [ ] 读 DEVELOPMENT_CONSTRAINTS.md（行为约束）
- [ ] 读 PROJECT_PLAN.md（开发计划）
- [ ] 跑 `git log --oneline -10` 看最近进度
- [ ] 跑 `git status` 确认工作树干净
- [ ] 跑 `pytest server/tests/` 确认测试全绿
- [ ] 跑 `start.bat` 端到端验证启动正常
- [ ] 把 §E 沟通模板贴给 Zcode（**第一条消息**）
- [ ] 收到 Zcode 状态报告后决定下一步

---

## H. 维护

- 本文件**不替代**规范三件套，只是"新会话暖场"
- 每次大进度推进时，可更新 §C 进度快照
- 每次切换 agent 时，更新 §E 沟通模板（如有变化）
- 已知问题解决后，从 §D 移走
- 临时决策如需锁定，提升到 AGENTS.md / PROJECT_PLAN.md（按 DEVELOPMENT_CONSTRAINTS.md §1.3 / §2.3 走修改流程）
