# Book Soul

> 小说 AI 写作桌面应用 · 人物卡驱动的本地优先创作工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2-blueviolet.svg)](https://tauri.app/)

## 项目简介

Book Soul 是一款为网文作者和严肃文学作者设计的 **AI 辅助写作桌面应用**。从灵感发现、人物设定、章节创作到质量检测、版本控制，提供完整创作闭环。

### 核心特色

- 🎭 **人物卡驱动一致性** — 所有创作严格按人物卡进行（性格 / 习惯 / 思维 / 关系 / 成长弧线）
- 🛠 **Skill/Tool 系统** — 预装 12 个工具（字数统计 / 敏感词 / 摘要 / 角色抽取 / 题材分类等）+ 用户自定义扩展
- 🤖 **双模式 LLM** — 云端（mimo 国内主用 / MiniMax / OpenAI）+ 本地（Ollama）
- 🔒 **本地优先** — 数据存本地 SQLite，支持加密导出
- 📚 **4 大模块** — 灵感园 / 创作 / 质量检测 / 仓库
- ✍️ **流式创作** — 章节生成 / 选区重写实时流式输出，Tiptap 富文本编辑
- 🔄 **版本控制** — 每次修改自动存版本，diff 视图对比，秒级回滚
- 📤 **多格式导出** — Markdown / HTML / Word（.docx）/ 备份 zip
- 🔍 **本地扫描** — 一键扫描本地小说目录批量导入

## 快速开始

### 用户（只想用应用）

1. 前往 [Releases](https://github.com/jeezee990-arch/book-soul/releases) 下载对应平台安装包
2. 安装后启动应用
3. 在**设置页**填入 LLM API Key（推荐 mimo 国内免 VPN）
4. 跟着灵感园三步流程（关键词 → 剧情 → 大纲）开始创作

### 开发者（想跑源码 / 二次开发）

#### 环境要求

- **Node.js** ≥ 20
- **Python** ≥ 3.11
- **Rust** ≥ 1.74（Tauri 2 要求）
- **pnpm** ≥ 9（`npm install -g pnpm`）
- **uv** ≥ 0.4（[安装](https://docs.astral.sh/uv/)）
- **Tauri 依赖**（Linux）：`libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev patchelf`

#### 安装

```bash
# 1. 克隆
git clone https://github.com/jeezee990-arch/book-soul.git
cd book-soul

# 2. 后端
cd server
uv sync
cd ..

# 3. 前端
cd apps/desktop
pnpm install
cd ../..
```

#### 启动（开发模式）

```bash
# 一键启动（后端 8765 + Vite 5173 + Tauri）
# Windows
.\Start Book Soul.vbs

# 或手动
# 终端 1：后端
cd server
uv run python -m src.main

# 终端 2：前端 + Tauri
cd apps/desktop
pnpm tauri dev
```

访问 http://127.0.0.1:1420（Tauri WebView）/ http://127.0.0.1:5173（Vite）

#### 测试

```bash
# 后端：487 个测试
cd server
uv run pytest

# 代码质量
uv run ruff check .

# 前端：构建验证
cd apps/desktop
pnpm build

# Tauri Rust
cd src-tauri
cargo check
```

## 目录结构

```
book-soul/
├── apps/desktop/              # Tauri + React 前端
│   ├── src/
│   │   ├── pages/            # 5 个主页面
│   │   │   ├── Inspiration/  # 灵感园
│   │   │   ├── Creation/     # 创作（Tiptap 编辑器）
│   │   │   ├── QualityCheck/ # 质检（recharts 雷达图）
│   │   │   ├── Library/      # 作品库 + 藏书馆 + 灵感库 + 本地扫描
│   │   │   ├── Skills/       # 12 个 Skill 执行面板
│   │   │   └── Settings/     # LLM / 主题 / 加密 / 备份恢复
│   │   ├── components/        # 共享组件（Layout / EmptyState / ErrorBoundary 等）
│   │   ├── api/              # 后端 API 的 TS 客户端
│   │   └── stores/           # Zustand
│   └── src-tauri/             # Rust 壳
├── server/src/                # FastAPI 后端
│   ├── api/                  # 11 个路由模块
│   ├── services/             # 业务服务
│   ├── models/               # SQLAlchemy ORM
│   ├── schemas/              # Pydantic
│   ├── core/                 # LLM / 质检 / 扫描 / Skill 抽象
│   └── db.py                 # SQLAlchemy async engine
├── config/
│   ├── prompts/              # 12 个 prompt 模板
│   ├── genres/               # 题材常识库
│   ├── wordbanks/            # 词库
│   └── llm.yaml              # LLM provider 配置
├── data/                      # 运行时数据（不入 git）
│   ├── book-soul.db
│   ├── novels/
│   └── logs/
├── docs/                      # 用户文档
└── .github/workflows/         # CI / Release
```

## 文档

- [用户指南](docs/USER_GUIDE.md) — 5 大模块详细使用
- [API 参考](docs/API.md) — 后端所有端点
- [架构设计](docs/ARCHITECTURE.md) — 模块划分 / 数据流 / 关键设计

## 路线图

| Phase | 状态 | 内容 |
|-------|------|------|
| 0 - 基础 | ✅ | Tauri 壳 + FastAPI + LLM 抽象 |
| 1 - CRUD | ✅ | Novel / Character / Chapter / Outline / Inspiration |
| 2 - 设置 | ✅ | LLM Provider / API Key / 主题 / 加密 |
| 3 - 灵感园 | ✅ | 题材 → 词 → 剧情 → 大纲 → 人物卡 → 导出 |
| 4 - 创作 | ✅ | Tiptap / 流式生成 / 选区重写 / 版本控制 / 多格式导出 |
| 5 - 质检 | ✅ | 5 维度并行评分（文笔 / 逻辑 / 节奏 / 一致性 / 题材）|
| 6 - 仓库 | ✅ | 灵感库 / 藏书馆 / 本地扫描 / Skill 系统基础 |
| 7 - 优化 | ✅ | 12 个 Skill / 错误边界 / 备份恢复 |
| 8 - 打包 | ✅ | Tauri 配置 / GitHub Actions Release |

## 贡献

欢迎 PR / Issue！提交前请：

1. `uv run pytest` 全过
2. `uv run ruff check .` 无 error
3. `pnpm build` 无 error
4. `cargo check` 无 error
5. 写明 commit message 关联 Phase / 模块

详见 [AGENTS.md](./AGENTS.md) 和 [DEVELOPMENT_CONSTRAINTS.md](./DEVELOPMENT_CONSTRAINTS.md)。

## 许可

MIT License — 详见 [LICENSE](LICENSE)。
