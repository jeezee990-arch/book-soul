# 贡献指南

感谢你愿意改进 Book Soul。这个项目目前是 **Windows 桌面应用**（Tauri 2 + FastAPI），
请先在 Windows 10/11 x64 上跑通 [README 的快速启动](README.md#快速启动)。

## 1. 环境准备

| 工具 | 版本 |
|---|---|
| Python | ≥ 3.11 |
| uv | ≥ 0.4 |
| Node.js | ≥ 22.13 |
| pnpm | 11.x（由 `packageManager` 锁定） |
| Rust | ≥ 1.74 |
| MSVC C++ Build Tools | 最新（勾选“使用 C++ 的桌面开发”） |
| WebView2 | Windows 10/11 自带或手动安装 |

```bash
git clone https://github.com/jeezee990-arch/book-soul.git
cd book-soul

# 后端：必须带 --all-packages --extra dev
uv sync --all-packages --extra dev

# 前端
cd apps/desktop && pnpm install && cd ../..
```

## 2. 本地检查

提交前至少跑完这五项：

```bash
cd server
uv run pytest -q --cov=src --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src/core src/services
```

```bash
cd apps/desktop
pnpm test
pnpm build
cd src-tauri && cargo check
```

如果有改动流式 / 章节生成 / 提示词，请同时更新对应的契约测试；
规范见 [AGENTS.md](AGENTS.md)。

## 3. 提交规范

- 一次提交只做一件事，commit message 用 `type(scope): 描述`
  （`feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `ci`）。
- **不要提交** `.env`、`data/`、`dist/`、`node_modules/`、数据库文件或任何真实 API Key。
- 新增/修改 `.ps1` 时必须保存为 **UTF-8 with BOM**（见 AGENTS.md §8.5）。
- 文档里的界面文案、测试数量、目录结构要和代码一起改，不要只改代码。

## 4. Pull Request

1. Fork 仓库，从 `main` 切分支：`feat/xxx`、`fix/xxx`、`docs/xxx`。
2. 完成改动并跑完第 2 节的检查。
3. 开 PR，说明改了什么、为什么改、怎么验证；关联 Issue（如果有）。
4. CI 必须全绿（backend / frontend / packaging-smoke）。

## 5. 发布流程

发布由 tag 触发 `.github/workflows/release.yml`，只构建 Windows NSIS 安装包。

1. 更新版本号（五处保持一致）：
   - `pyproject.toml`
   - `server/pyproject.toml`
   - `apps/desktop/package.json`
   - `apps/desktop/src-tauri/tauri.conf.json`
   - `apps/desktop/src-tauri/Cargo.toml`
2. 更新 `CHANGELOG.md`。
3. 同步锁文件：`uv lock`、`cd apps/desktop && pnpm install --lockfile-only`、`cargo check`。
4. 提交并推送 `main`，确认 CI 通过。
5. 打 tag 并推送：

   ```bash
   git tag -a v0.1.1 -m "Book Soul v0.1.1"
   git push origin main --tags
   ```

6. 等 Release workflow 完成，确认 Releases 页面有 `Book.Soul_0.1.1_x64-setup.exe`
   （GitHub 会把上传文件名里的空格显示为 `.`）。

> 不要在版本号没对齐时打 tag —— 安装包名、程序内版本、CHANGELOG 会对不上。
