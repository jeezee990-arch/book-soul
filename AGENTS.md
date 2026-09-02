# AGENTS.md - Book Soul 项目规范

> 这是项目根目录的强制规范文件。所有参与本项目的 agent（minimax code 等）必须遵守。

## 项目概述

**Book Soul** - 小说 AI 写作桌面应用
- 帮助网文/严肃文学作者从灵感发现到章节创作的全流程
- 核心特色：人物卡驱动一致性 + Skill/Tool 系统 + 双模式 LLM（云端 + 本地 Ollama）
- 部署：Tauri 桌面应用 + GitHub 公开仓库
- 工作目录：`C:\Users\JZ\Desktop\Book Soul`

## 技术栈（强制）

| 层级 | 技术 | 禁止替代 |
|------|------|----------|
| 桌面壳 | Tauri 2 | ❌ Electron |
| 前端框架 | React 18 + TypeScript + Vite | ❌ Vue / Svelte |
| 状态管理 | Zustand | ❌ Redux |
| UI 库 | shadcn/ui + Tailwind CSS | - |
| 编辑器 | Tiptap | ❌ Slate / Lexical |
| 后端 | Python 3.11+ + FastAPI | ❌ Flask / Django |
| ORM | SQLAlchemy 2 | ❌ Tortoise ORM |
| 数据库 | SQLite + aiosqlite | ❌ PostgreSQL |
| 向量库 | ChromaDB | ❌ Pinecone / Milvus |
| LLM 抽象 | 自研 Protocol（~200 行） | ❌ LangChain / LlamaIndex |
| Python 包管理 | uv | ❌ pip / poetry |
| Node 包管理 | pnpm | ❌ npm / yarn |
| 加密 | cryptography.Fernet（可选） | - |
| API Key 存储 | 系统 Keyring | ❌ 入 .env |
| Lint | ruff | ❌ flake8 / black |
| 类型检查 | mypy | - |
| 测试 | pytest | - |
| Pre-commit | pre-commit + ruff + gitleaks | - |
| CI | GitHub Actions | - |

## 目录约定

```
book-soul/
├── apps/desktop/        # Tauri + React 前端
├── server/src/          # Python 后端
│   ├── api/             # FastAPI 路由
│   ├── core/            # 核心子系统（llm/memory/skills/...）
│   ├── models/          # SQLAlchemy ORM
│   ├── schemas/         # Pydantic
│   └── services/        # 业务逻辑
├── config/              # 配置文件
│   ├── llm.yaml         # LLM provider 配置
│   ├── genres/          # 题材常识库
│   ├── wordbanks/       # 词库
│   └── prompts/         # 提示词
├── data/                # 运行时（不入 git）
└── docs/                # 文档
```

**业务代码规则**：
- 所有业务逻辑在 `server/src/services/`，不在 api 路由里直接写
- 数据库操作走 `models/`，不在 service 里写原生 SQL
- 文件 IO 集中在 service 层，不在 core/ 里散落

## 命名规范

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
| 数据库表 | 复数 snake_case | `characters`, `chapter_versions` |

## 严格禁止

- ❌ 不用 LangChain / LlamaIndex
- ❌ 不用 Flask / Django
- ❌ 不用 Electron
- ❌ 前端代码不硬编码任何 API Key
- ❌ .env / .env.local 不提交 git
- ❌ 不用 print 调试（用 loguru）
- ❌ 单一函数不超 200 行
- ❌ SQL 不用参数化（必须用 ORM）
- ❌ 不引用未确认的库/函数（先 Google 确认存在）
- ❌ 不跳过测试写新功能
- ❌ 不用 Tailwind 之外的 CSS 方案（除非组件库强依赖）
- ❌ 不引入非必要依赖

## 提示词管理

所有 prompt 必须在 `config/prompts/*.yaml` 用 YAML 管理：

```yaml
version: 1  # 必带
changelog:  # 改动时记录
  - "v1: 初始版本"
prompt: |
  ...
```

**绝对不要**把 prompt 散落在 Python 代码里。

## 安全规范

- ✅ 所有 SQL 用 SQLAlchemy ORM（自动参数化）
- ✅ 所有文件操作检查路径（防越界，`Path.resolve()` 后必须以 `data_dir` 开头）
- ✅ 所有网络请求加超时（`httpx.AsyncClient(timeout=30.0)`）
- ✅ 所有用户输入校验（Pydantic schema）
- ✅ API Key 存系统 Keyring，不入配置文件
- ✅ 章节字数硬限 1k-8k
- ✅ context_window 必须 ≥ 32k 才能生成章节（model_checker）
- ✅ 加密默认关闭，开启后警告用户备份风险

## 测试规范

每个 service / 关键函数必须配 pytest 单元测试：

```python
# tests/test_character_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_create_character(session: AsyncSession):
    ...
```

**测试要求**：
- 业务逻辑必须有测试
- 边界条件（空、None、超长）必须有测试
- 错误路径（异常抛出）必须有测试

## 模块代码量控制

- 单个模块产出代码不超过 **300 行**（不含测试和注释）
- 超出必须拆分

## 提交流程

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
```

## 模块开发流程

每个模块按以下顺序：

1. **测试先行**（如适用）：先写 `test_xxx.py` 测试用例
2. **实现代码**：`src/xxx.py` 实现
3. **本地验证**：`pytest` + `ruff check`
4. **commit**：清晰消息
5. **用户验证**：给用户"用户验证清单"

## 沟通原则

- 简洁直接，不啰嗦
- 不确定就问，不要瞎猜
- 引用代码用 `file_path:line` 格式
- 完成后给"用户验证清单"和 commit 消息建议

## 参考资料

- 完整开发计划：`PROJECT_PLAN.md`
- 用户准备清单：`USER_CHECKLIST.md`
- 安全策略：`SECURITY.md`
