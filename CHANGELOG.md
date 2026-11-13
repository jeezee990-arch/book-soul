# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.1] - 2026-11-13

### Added

- 新增 `CONTRIBUTING.md`、`CHANGELOG.md`、`.gitattributes`、Issue / PR 模板。
- README 增加 CI 徽章、Windows 运行要求和 SmartScreen 说明。
- 发布流程改为 Windows-only 的 NSIS 构建，并在 tag 上自动创建 GitHub Release。

### Changed

- 前端工具链统一到 Node.js 22.13+ / pnpm 11（`packageManager` 锁定）。
- 文档中的 `uv sync` 全部改为 `uv sync --all-packages --extra dev`。
- `docs/START_GUIDE.md` 去掉个人绝对路径，改为面向所有开发者的启动/验收指南。
- 刷新 `apps/desktop/README.md` 与 `server/README.md`，与当前目录和命令保持一致。

### Fixed

- 修复 CI 前端 `pnpm install --frozen-lockfile` 因 workspace 缺 `packages` 字段失败。
- 修复 Release workflow 缺少 dev 依赖、在非 Windows runner 调用 PowerShell 的问题。
- 修正 `SECURITY.md` 中“CI 已跑 gitleaks”的不准确表述。
- 清理 `.gitignore` 重复条目。

## [0.1.0] - 2026-09-05

### Added

- 首个版本：Tauri 2 桌面壳、FastAPI 后端、人物卡驱动写作、
  流式章节生成 / 重写、大纲与人物卡生成、版本回滚、素材库、本地扫描、
  Skill 系统、多格式导出。
