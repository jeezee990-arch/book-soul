# Book Soul

> 小说 AI 写作桌面应用 · 人物卡驱动的本地优先创作工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2-blueviolet.svg)](https://tauri.app/)

## 项目简介

Book Soul 是一款为网文作者和严肃文学作者设计的 **AI 辅助写作桌面应用**。

### 核心特色

- 🎭 **人物卡驱动一致性** — 所有创作严格按人物卡进行，自动追踪性格变化
- 🛠 **Skill/Tool 系统** — 预装 12 个工具 + 用户自定义扩展
- ☁️🌥 **双模式 LLM** — 云端（minimax-M3 / OpenAI / Claude）+ 本地（Ollama）
- 🔒 **本地优先** — 数据存本地，支持加密
- 📚 **4 大模块** — 灵感园 / 创作 / 质量检测 / 仓库

## 快速开始

### 用户（只想用应用）

1. 前往 [Releases](https://github.com/JEE/book-soul/releases) 下载对应平台安装包
2. 安装后启动
3. 在设置页填入 LLM API Key
4. 开始创作！

### 开发者（想参与开发）

```bash
# 1. 克隆仓库
git clone https://github.com/JEE/book-soul.git
cd book-soul

# 2. 安装依赖
# Python (需要 Python 3.11+, uv)
cd server
uv sync --all-extras
cd ..

# Node (需要 Node 20+, pnpm)
cd apps/desktop
pnpm install
cd ../..

# 3. 配置环境
cp .env.example .env
# 编辑 .env 填入 API Key

# 4. 启动开发模式
# 终端 1：启动 Python 后端
cd server && uv run python -m src.main

# 终端 2：启动 Tauri 桌面应用
cd apps/desktop && pnpm tauri dev
```

详细开发文档见：
- [PROJECT_PLAN.md](PROJECT_PLAN.md) - 完整开发计划
- [USER_CHECKLIST.md](USER_CHECKLIST.md) - 用户准备清单
- [DEVELOPMENT_CONSTRAINTS.md](DEVELOPMENT_CONSTRAINTS.md) - 开发行为约束（agent 必读）
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) - 用户手册（开发中）
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 架构说明（开发中）

## 技术栈

- **桌面壳**: Tauri 2
- **前端**: React 18 + TypeScript + Vite + Tailwind + shadcn/ui + Tiptap
- **后端**: Python 3.11+ / FastAPI / SQLAlchemy 2 / SQLite
- **LLM 抽象**: 自研 Protocol（不用 LangChain）
- **向量库**: ChromaDB
- **包管理**: uv (Python) + pnpm (Node)

## 项目结构

```
book-soul/
├── apps/desktop/          # Tauri + React 前端
├── server/                # Python 后端
├── config/                # 配置文件（LLM/题材/词库/提示词）
├── docs/                  # 文档
├── data/                  # 运行时数据（不入 git）
└── .github/workflows/     # CI/CD
```

## 贡献

欢迎贡献代码、报告 Bug、提出建议！

开发前请阅读：
- [AGENTS.md](AGENTS.md) - 项目技术规范（强制）
- [DEVELOPMENT_CONSTRAINTS.md](DEVELOPMENT_CONSTRAINTS.md) - 开发行为约束（强制）
- [PROJECT_PLAN.md](PROJECT_PLAN.md) - 开发计划
- [SECURITY.md](SECURITY.md) - 安全策略

## 路线图

- [x] Phase 0: 环境与基建
- [ ] Phase 1: 核心后端服务
- [ ] Phase 2: 桌面壳 + 前端骨架
- [ ] Phase 3: 灵感园 - 开新书
- [ ] Phase 4: 创作
- [ ] Phase 5: 质量检测
- [ ] Phase 6: 仓库
- [ ] Phase 7: 优化与 Skill 完善
- [ ] Phase 8: 打包与发布

## 许可证

[MIT](LICENSE)

## 致谢

- LLM 能力：[minimax](https://api.minimaxi.com/)
- 桌面框架：[Tauri](https://tauri.app/)
- 编辑器：[Tiptap](https://tiptap.dev/)
- UI 组件：[shadcn/ui](https://ui.shadcn.com/)
