# Book Soul Desktop

Tauri 2 + React 18 + TypeScript + Vite + Tailwind 桌面应用。

## 启动

```bash
# 在 apps/desktop/ 目录下
pnpm install
pnpm tauri dev
```

首次 `tauri dev` 会编译 Rust 端，**可能需要 5-10 分钟**下载并编译 crates。

## 端口约定

- Vite dev server: `127.0.0.1:5173`
- Tauri HMR: `127.0.0.1:5183`
- Python 后端（Phase 0.7 暂未连接）：`127.0.0.1:8765`

## 目录结构

```
apps/desktop/
├── src/                 ← React 前端
│   ├── main.tsx         ← React 入口
│   ├── App.tsx          ← 根组件
│   └── styles.css       ← Tailwind
├── src-tauri/           ← Rust 端
│   ├── src/
│   │   ├── main.rs      ← 二进制入口
│   │   └── lib.rs       ← 业务逻辑（含 Tauri 命令）
│   ├── capabilities/    ← 权限配置
│   ├── icons/           ← 应用图标
│   ├── tauri.conf.json
│   └── Cargo.toml
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

## 当前状态

模块 0.7：Tauri 壳可启动，Rust 端暴露 `ping` 命令，前端能调用并显示结果。
后续模块会接入 Python 后端（HTTP 客户端）、文件系统、设置持久化等。
