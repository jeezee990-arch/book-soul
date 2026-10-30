# Book Soul 排障与应急手册

> 出问题时查这里。安装步骤见 [README](../README.md)，界面操作见 [用户指南](./USER_GUIDE.md)，
> 启动验证清单见 [启动指南](./START_GUIDE.md)。

---

## 1. 先看日志

90% 的问题日志里就有答案。**桌面端 release 没有控制台**（`eprintln!` 会丢），
日志写在数据目录下：

| 文件 | 内容 |
|---|---|
| `data/logs/desktop.log` | 桌面端启动日志（**后端拉不起来时真实原因在这**） |
| `data/logs/server.log` | 后端业务日志（LLM 调用、生成耗时） |
| `data/logs/backend.log` | 后端进程原始输出（Python 异常栈） |

开发态实时跟踪：

```powershell
Get-Content data\dev\logs\server.log -Tail 50 -Wait
```

打包态（便携版）：

```powershell
Get-Content "dist\Book Soul\data\logs\desktop.log" -Tail 50 -Wait
```

> `desktop.log` 带 UTF-8 BOM，用记事本打开中文不乱码。

---

## 2. 常见问题

### 2.1 双击 exe 没反应 / 报「找不到后端可执行文件」

按顺序查：

1. **sidecar 还在吗** —— `dist\Book Soul\book-soul-server.exe` 必须和 `Book Soul.exe` 同级
2. **日志说了什么** —— `dist\Book Soul\data\logs\desktop.log`
3. **被杀毒软件拦了** —— PyInstaller 打包的 exe 常被误报，加信任或换路径再试
4. **端口冲突** —— 打包版用随机空闲端口，不该冲突；若报端口问题看 `backend.log`

### 2.2 开发模式起不来（Tauri）

| 症状 | 原因 | 处理 |
|---|---|---|
| `cargo not found` | Rust 没装或不在 PATH | 装 [rustup](https://rustup.rs/)，或确认 `~\.cargo\bin` 在 PATH |
| `linker not found` | 缺 MSVC | 装 Visual Studio Build Tools + **C++ 工作负载** |
| 窗口白屏 | WebView2 缺失（Windows 10） | 装 [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) |
| 后端起不来 | `.venv` 缺失 | 仓库根执行 `uv sync` |

### 2.3 端口 8765 被占用（开发模式）

```powershell
# 找占用进程
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess
Get-Process -Id <PID>
```

`scripts\start_backend.ps1` 会自动杀掉占用 8765 的**残留 python 进程**并重启，
一般不用手工处理。真要换端口改 `.env` 的 `BOOK_SOUL_PORT`。

> 打包版**不用管端口** —— Rust 侧每次分配随机空闲端口。

### 2.4 LLM 调用失败

1. **Key 对不对** —— 设置页填的 Key 对应哪个 provider？`config/llm.yaml` 里
   `api_key_env` 写明了环境变量名
2. **网络通不通** —— provider 是否需要 VPN（`minimax` 海外节点需要，`mimo` 国内直连）
3. **模型名还在不在** —— 上游下线的模型名会报 404。设置页点「刷新列表」重新拉
4. **余额 / 额度** —— 429 是配额问题，不是代码问题
5. **单独测**：
   ```bash
   curl -X POST https://api.xiaomimimo.com/v1/chat/completions \
     -H "Authorization: Bearer $MIMO_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"mimo-v2.6-pro","messages":[{"role":"user","content":"hi"}]}'
   ```

### 2.5 顶栏模型状态灯一直转圈 / 显示「不可用」

- **不可用** = 探测请求失败。健康探测**带 API Key**，所以能区分「服务挂了」和「Key 错了」
- **一直转圈** = 探测超时。探测结果有 60s TTL 缓存 + stale-while-revalidate，
  不该让前端干等网络；若真卡住看 `server.log` 里的探测记录
- 换 Key / 换 provider 后必须**重启应用**或点「刷新列表」绕过缓存

### 2.6 生成时界面一直转圈，什么都不出来

先确认是**哪一类失败** —— NDJSON 流有两种失败长得不一样：

| 来源 | 事件形状 | 界面表现 |
|---|---|---|
| transport（HTTP 非 2xx / body 空 / 解析失败） | `{"error": "..."}` | 应该弹错 + 回退 |
| server（后端流内错误帧） | `{"event": "error", "message": "..."}` | 应该弹错 + 回退 |

如果界面**永远转圈**，说明流消费方没处理某一种 —— 这是代码 bug，提交 Issue 时
附上 `server.log` 里对应时刻的日志。

### 2.7 三个剧情版本不是同时出来的 / 某张卡一直转圈

- **内容实时透传**：谁先回谁先显示，这是正常的
- 只有「这个版本好了」的**完成提示**按下标保序
- 如果某张卡单独转圈且别的已完成 → 那张卡对应的版本**失败了**，看它有没有标红报错

### 2.8 章节生成卡住 / 字数不达标

1. **人物卡是不是空卡** —— 空卡会让模型没东西可写
2. **大纲是不是太短** —— 至少要有一段话
3. **目标字数** —— 章节硬限 1k-8k，在 `config/llm.yaml` 的 `chapter_limits`
4. **模型是否支持** —— `context_window` 必须 ≥ 32k 才能生成章节，
   设置页会弹警告

### 2.9 数据库锁定 / 表不存在 / 数据错乱

```powershell
# ⚠️ 先备份！
Copy-Item data\dev\book-soul.db data\dev\book-soul.db.bak
Remove-Item data\dev\book-soul.db
# 重启应用 —— 会自动建表 + 补列 + 清孤儿行
```

> `init_db()` 做三件事：建缺失的表 → ALTER 补缺失的列 → 清「父行已删」的孤儿行。
> 任何一步失败都**不会**阻断启动，所以数据错乱时删库重建通常能解决。

### 2.10 打包失败

| 症状 | 检查 |
|---|---|
| NSIS 打包失败 | `tauri.conf.json` 的 `externalBin`（`binaries/book-soul-server`）是否已生成 |
| sidecar 找不到 | 先跑 `scripts\build_sidecar.ps1` |
| 改了前端但界面没变 | **Tauri 把前端资源嵌进 exe 了** —— 必须重新打包 |

### 2.11 提交被 pre-commit 拦下

```powershell
# 看是哪个 hook 失败
pre-commit run --all-files
```

常见：

- **ruff** —— `uv run ruff check . --fix` 自动修
- **gitleaks** —— 引用了看起来像 key 的字符串。测试用的假 key 加 `# gitleaks:allow`；
  要是**真的 key，立刻撤销重生成**（见 §3.1）

### 2.12 CI 失败

本地按 CI 的顺序重现：

```bash
cd server && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd apps/desktop && pnpm test && pnpm build
cd apps/desktop/src-tauri && cargo check
```

CI 有三个 job：`backend`（lint+test+coverage）、`frontend`（vitest+build+cargo check）、
`packaging-smoke`（真打 sidecar → 启动 → 探活 → 检查数据目录）。

---

## 3. 紧急情况

### 3.1 API Key 泄露了

1. **立刻**在 provider 后台撤销该 Key
2. 生成新 Key
3. 检查是否进了 git 历史：`git log -p -S "<泄露的 key 前 8 位>"`
4. 若是**公开仓库**且已推送 → 通知 GitHub（Support）协助清理
5. 确认账单没有异常消费

> `pre-commit` 的 gitleaks 钩子 + CI 二次扫描是双保险，
> 但**已经推出去的东西它拦不住** —— 所以撤销 Key 永远排在第一位。

### 3.2 数据丢了

| 情况 | 能不能救 |
|---|---|
| 应用卸载了，数据目录还在 | 直接重装应用即可 |
| 数据目录被删了，没备份 | **不能**。默认不加密，本地 SQLite 无云端副本 |
| 备份 zip 还在 | 设置 → 数据与备份 → 从备份恢复 → 重启应用 |

> **定期备份整个数据目录**，不只是 `book-soul.db`：
> `secrets/`（DPAPI 加密的 Key）、`wordbanks/`、`skills/` 也在同一目录下。

### 3.3 应用完全起不来，重置环境

```powershell
# ⚠️ 删前确保你已有备份！
Remove-Item -Recurse -Force data\
Remove-Item -Recurse -Force apps\desktop\src-tauri\target
Remove-Item -Recurse -Force apps\desktop\node_modules
Remove-Item -Recurse -Force .venv

# 然后重装
uv sync                                    # 仓库根
cd apps\desktop; pnpm install; cd ..\..\  # 前端
```

### 3.4 磁盘空间告急

工作区能到 **9.6 GB**，几乎全是构建缓存（成品只有 36 MB）：

| 目录 | 大小 | 删了会怎样 |
|---|---|---|
| `apps\desktop\src-tauri\target\` | **8.7 GB** | 重编译（debug 几分钟，release 20-40 分钟） |
| `data\dev\_smoke\` | 371 MB | 无（Edge 走查残留的浏览器 profile） |
| `server\build` + `server\dist` + `server\.mypy_cache` | 113 MB | PyInstaller 中间产物 + mypy 缓存 |
| `.venv` | 154 MB | `uv sync` 重装 |
| `apps\desktop\node_modules` | 184 MB | `pnpm install` 重装 |

```powershell
# 保留开发环境，只清构建缓存（9.6 GB → 约 0.4 GB）
Remove-Item -Recurse -Force apps\desktop\src-tauri\target
Remove-Item -Recurse -Force data\dev\_smoke
Remove-Item -Recurse -Force server\build, server\dist, server\.mypy_cache
```

**防复发**：把 Rust 构建目录挪出仓库 —— 在
`apps\desktop\src-tauri\.cargo\config.toml` 写：

```toml
[build]
target-dir = "C:/Users/<你>/.cargo-target/book-soul"
```

这样 Rust 的 8.7 GB 根本不落在项目目录里。

---

## 4. 数据目录在哪

| 运行模式 | 数据目录 | 怎么找 |
|---|---|---|
| **打包版（便携）** | `<Book Soul.exe 同级>/data/` | 设置 → 数据与备份 → 「打开数据目录」 |
| **开发模式（脚本）** | `<仓库根>/data/dev/` | `scripts\dev.ps1` 会设 `BOOK_SOUL_DATA_DIR` |
| **开发模式（手工起）** | `~/Documents/BookSoul/` | 未设 `BOOK_SOUL_DATA_DIR` 时的回落值 |

设置页「数据与备份」分区会显示**当前实际生效的路径**，以它为准。
