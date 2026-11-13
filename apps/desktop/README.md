# Book Soul Desktop

Tauri 2 + React 18 + TypeScript + Vite + Tailwind CSS 桌面端。

## 启动

```bash
# 仓库根：安装后端依赖（venv 落在仓库根 .venv）
uv sync --all-packages --extra dev

cd apps/desktop
pnpm install
pnpm tauri dev
```

首次 `tauri dev` 会编译 Rust 端，通常需要 5–10 分钟；之后走缓存会快很多。

> `pnpm tauri dev` 的 `beforeDevCommand` 会先拉起 Python 后端并等 `/ping` 就绪，再启动 Vite。
> 手动启动后端、构建独立版的步骤见仓库根 `README.md` 和 `docs/START_GUIDE.md`。

## 端口约定

- Vite dev server：`127.0.0.1:5173`
- Python 后端：开发模式默认 `127.0.0.1:8765`；Tauri 优先复用它，没有就分配随机空闲端口并下发给前端
- 前端**不得硬编码**后端地址，统一走 `src/api/backend.ts`

## 目录结构

```
apps/desktop/
├── src/
│   ├── api/          # 后端 API 客户端（含 NDJSON 流解析）
│   ├── components/   # 通用组件 + shadcn/ui 原子组件
│   ├── pages/        # 写作 / 开新书 / 素材库 / 设置
│   ├── stores/       # Zustand 状态
│   ├── lib/          # 纯函数工具
│   └── App.tsx       # HashRouter 路由表
├── src-tauri/        # Rust 桌面壳（sidecar / 窗口 / 日志）
└── scripts/          # Node 自证脚本（不依赖浏览器）
```

## 常用命令

```bash
pnpm test          # vitest
pnpm build         # tsc + vite build
cd src-tauri && cargo check
```

## 相关文档

- [快速开始](../../README.md#快速启动)
- [启动与验收指南](../../docs/START_GUIDE.md)
- [项目结构](../../docs/PROJECT_STRUCTURE.md)
