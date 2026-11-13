## 改了什么

<!-- 一句话说明这个 PR 的目的 -->

## 为什么改

<!-- 关联 Issue：Closes #xxx -->

## 怎么验证

- [ ] `cd server && uv run pytest`
- [ ] `cd server && uv run ruff check . && uv run ruff format --check .`
- [ ] `cd apps/desktop && pnpm test && pnpm build`
- [ ] `cd apps/desktop/src-tauri && cargo check`
- [ ] 手动走查（如果是 UI / 流式改动，写明步骤）

## 检查清单

- [ ] 没有提交 `.env`、`data/`、`dist/` 或真实 API Key
- [ ] 文档（README / USER_GUIDE / CHANGELOG）已同步
- [ ] 新增或修改的 `.ps1` 是 UTF-8 with BOM
- [ ] 没有无关的格式化 / 重命名噪音
