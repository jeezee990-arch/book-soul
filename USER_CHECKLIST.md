# Book Soul · 用户准备清单（USER_CHECKLIST）

> 配套 `PROJECT_PLAN.md` 使用
> 把你**人工要做**的事情和**agent 开发做**的事情分清楚

---

## 0. 这份清单是干什么的

你作为项目发起人，主要做 3 类事：
1. **装环境**（一次性，1-2 天）
2. **申请 API Key**（一次性，1-2 天）
3. **验证功能**（贯穿开发，每周 1-2 次）

agent（minimax code）会做：
1. 写代码
2. 跑测试
3. 配置 CI
4. 部署打包

---

## Part A：环境准备（一次性，约 1-2 天）

### A.1 系统要求

- **操作系统**：Windows 10/11（推荐）、macOS 12+、Ubuntu 20.04+
- **磁盘空间**：至少 5GB（开发环境 + 模型缓存）
- **内存**：至少 8GB（跑本地 LLM 建议 16GB+）

### A.2 必装工具清单

| 工具 | 版本 | 安装地址 | 验证命令 |
|------|------|----------|----------|
| **Python** | 3.11+ | https://www.python.org/downloads/ | `python --version` |
| **Node.js** | 20 LTS | https://nodejs.org/ | `node --version` |
| **pnpm** | 9+ | `npm install -g pnpm` | `pnpm --version` |
| **Rust** | stable | https://rustup.rs/ | `rustc --version` |
| **uv** | latest | `pip install uv` | `uv --version` |
| **Git** | 2.40+ | https://git-scm.com/ | `git --version` |
| **VS Code** | latest | https://code.visualstudio.com/ | - |
| **Visual Studio Build Tools** | 2022 | https://visualstudio.microsoft.com/downloads/（选 "C++ build tools" 工作负载） | - |

### A.3 可选工具

| 工具 | 用途 | 安装 |
|------|------|------|
| **Ollama** | 本地 LLM 推理 | https://ollama.com/ |
| **LM Studio** | 图形化本地 LLM | https://lmstudio.ai/ |

### A.4 安装后必须验证的 6 件事

打开 PowerShell 依次运行（每行一个命令）：

```powershell
python --version        # 应显示 3.11.x 或更高
node --version          # 应显示 v20.x.x
pnpm --version          # 应显示 9.x.x
rustc --version         # 应显示 rustc 1.xx.x
uv --version            # 应显示 uv 0.x.x
git --version           # 应显示 git version 2.4x.x
```

如果其中任何一个失败，**先解决再继续**。

### A.5 Windows 特别注意事项

1. **Python 安装时**勾选 "Add Python to PATH"
2. **Visual Studio Build Tools** 必须装 "C++ build tools" 工作负载（Rust 编译需要）
3. **WebView2 Runtime** Windows 11 自带；Windows 10 需要手动装：https://developer.microsoft.com/microsoft-edge/webview2/
4. **路径不含中文**（虽然本项目在中文路径下，但 cargo/Rust 可能出问题）

### A.6 VS Code 推荐插件

- Python（Microsoft）
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Tauri
- GitLens
- Error Lens
- Chinese Language Pack（中文界面）

---

## Part B：账号与 API Key（约 1-2 天）

### B.1 GitHub 账号

- 注册：https://github.com/
- 创建 Personal Access Token（PAT）：
  1. GitHub → 右上角头像 → Settings
  2. 左侧最下方 → Developer settings
  3. Personal access tokens → Tokens (classic) → Generate new token
  4. Note 填 `book-soul-dev`
  5. Expiration 选 `90 days` 或 `No expiration`
  6. 勾选 `repo` 和 `workflow`
  7. Generate token
  8. **立即复制并保存到密码管理器**（关掉页面就再也看不到）

### B.2 LLM API Key

#### 主用：minimax-M3（1M 上下文）

- 注册：https://api.minimaxi.com/
- 申请 API Key
- 记录两个值：
  - `MINIMAX_API_KEY=sk-xxx`
  - `MINIMAX_BASE_URL=https://api.minimaxi.com/v1`

#### 备用：OpenAI / Anthropic（至少 1 个）

- **OpenAI**: https://platform.openai.com/
  - 申请 API Key
  - 记录：`OPENAI_API_KEY=sk-xxx`
- **Anthropic**: https://console.anthropic.com/
  - 申请 API Key
  - 记录：`ANTHROPIC_API_KEY=sk-ant-xxx`

### B.3 可选 Key

- **Tavily**（网络搜索）：https://tavily.com/
  - `TAVILY_API_KEY=tvly-xxx`
- **LangSmith**（调试追踪）：https://smith.langchain.com/
  - `LANGSMITH_API_KEY=lsv2-xxx`

### B.4 填入 .env

1. 在项目根目录打开 PowerShell
2. 复制示例文件：
   ```powershell
   cp .env.example .env
   ```
3. 用 VS Code 或记事本编辑 `.env`，填入真实 Key
4. **重要**：
   - `.env` 永远不被 git 跟踪（已配 `.gitignore`）
   - 每次提交前 `git status` 检查 .env 不在列表里
   - 提交时会自动跑 `gitleaks` 拦截 Key 泄露

---

## Part C：素材准备（贯穿开发过程）

### C.1 质量检测测试样本

准备 5-10 本完整小说（任意题材）：

- 每本 ≥ 10 章
- 存到 `~/Documents/test-novels/`
- Phase 5 质量检测时使用

### C.2 词库参考

如有余力，可先收集（**按 JEE 决策的优先级**）：

- 修仙经典词条 800+（P0，最高优先级）
- 都市经典词条 500+（P1）
- 悬疑经典词条 500+（P2）
- 言情经典词条 500+（P3）

Phase 3 词库系统时使用。

### C.3 本地小说扫描

如果你电脑里已有小说：

- 整理路径到 `~/Documents/我的小说/`
- Phase 6 扫描接入时使用

---

## Part D：每次开发对话模板

### D.1 通用模板（新对话开头用）

```
我要做 Book Soul 项目（小说 AI 写作桌面应用）。

完整计划在项目根目录 PROJECT_PLAN.md 和 USER_CHECKLIST.md。

本次任务：
- 阶段：Phase X
- 模块：模块 X.Y
- 目标：<一句话目标>
- 验收标准：<怎么验证完成>

请：
1. 先读取 PROJECT_PLAN.md 中 Phase X 模块 X.Y 部分
2. 列出本模块要创建/修改的文件清单
3. 按计划逐步实施
4. 完成后运行 ruff + pytest + pre-commit
5. 给出我需要在 UI 或功能上人工验证的点
6. 给出 commit 消息建议
```

### D.2 bug 反馈模板

```
Phase X 模块 X.Y 出现 bug。

错误信息：
<粘贴完整错误>

复现步骤：
1. ...
2. ...

期望：...
实际：...

请：
1. 定位问题
2. 修复
3. 加测试防止回归
4. 验证修复
```

### D.3 续写提示

如果上次的对话太长/上下文满了，开新对话时：

```
继续 Book Soul 项目 Phase X 模块 X.Y 的开发。

上次进度：<简短描述>

请读取 PROJECT_PLAN.md，先确认本模块进度，然后继续。
```

### D.4 修改计划书的模板

```
我看了 PROJECT_PLAN.md，想调整：
- Phase X 模块 Y 改成 <新方案>
- 删掉 <某功能>
- 加 <某新功能>

理由：<为什么>

请更新 PROJECT_PLAN.md 和 USER_CHECKLIST.md，并告诉我影响。
```

---

## Part E：每个阶段的检验方法

### E.1 代码层面（agent 自动跑）

每次新对话开始时让 agent 跑：

- `pre-commit run --all-files` —— 必须全过
- `pytest` —— 必须全过
- `ruff check .` —— 必须全过
- `mypy src` —— 警告可接受，错误不接受

### E.2 功能层面（用户必须测）

每个模块完成，agent 会列出"用户验证清单"，用户按清单手动测试：

| 模块 | 验证动作 |
|------|----------|
| Phase 0.3 | 浏览器打开 http://127.0.0.1:8765/docs 看到 Swagger |
| Phase 0.7 | 运行 `pnpm tauri dev` 看到窗口 |
| Phase 0.10 | 点击"测试 LLM"按钮看到真实回复 |
| Phase 1.1 | 用 curl 测试 /novels 接口 CRUD |
| Phase 3.3 | 选 5 个灵感词 → 生成 3 个剧情 → 看到结果 |
| Phase 4.3 | 点击"生成章节" → 看到流式输出（字一个个蹦出来） |
| Phase 4.4 | 选中一段 → 输入提示词 → AI 重写 → 内容替换 |
| Phase 4.6 | 修改内容 → 看版本历史 → 对比 → 回滚 |
| Phase 5.2 | 选章节 → 检测 → 看雷达图 + 问题列表 |
| Phase 6.3 | 配置扫描目录 → 看到检测到的小说 → 导入 |

### E.3 集成测试（贯穿）

- **数据流测试**：UI 操作 → 后端 → DB 写入 → 重新读出正确
- **错误处理测试**：断网、LLM 超时、key 错误时应用不崩
- **重启测试**：关闭应用再打开，数据还在

---

## Part F：常见问题

### F.1 启动报错 "ModuleNotFoundError"

**原因**：依赖没装
**解决**：`cd server && uv sync`

### F.2 pre-commit 拦截了 commit

**原因**：代码风格不对或泄露 key
**解决**：
```bash
# 看具体哪个 hook 失败
pre-commit run --all-files
# 修复后再 commit
```

### F.3 LLM 调用失败

**排查**：
1. `.env` 里 API Key 是否正确
2. 网络是否能访问 provider
3. 余额是否充足
4. 用 curl 单独测试：
   ```bash
   curl -X POST https://api.minimaxi.com/v1/chat/completions `
     -H "Authorization: Bearer $MINIMAX_API_KEY" `
     -H "Content-Type: application/json" `
     -d '{"model":"MiniMax-M3","messages":[{"role":"user","content":"hi"}]}'
   ```

### F.4 Tauri 启动失败

**排查**：
1. Rust 是否装好
2. Visual Studio Build Tools 是否装（C++ 工作负载）
3. WebView2 是否装（Windows 11 自带，10 需要手动装）

### F.5 章节生成卡住

**排查**：
1. 人物卡是否合理（不能是空卡）
2. 大纲是否太短（至少一段话）
3. LLM provider 是否稳定
4. 日志：`Get-Content data/logs/server.log -Tail 50 -Wait`

### F.6 桌面应用打包失败

**排查**：
1. icon 是否准备
2. 平台工具链是否齐全
3. `tauri.conf.json` identifier 是否正确

### F.7 GitHub Actions 失败

**排查**：
1. 看具体哪个 step 失败
2. 本地重现：
   ```bash
   ruff check .
   pytest
   mypy src
   ```
3. 修复后 push 自动重跑

### F.8 提交时 gitleaks 报警

**说明**：可能你引用了某个看起来像 key 的字符串
**解决**：
- 如果是测试用的假 key，加 `# gitleaks:allow` 注释
- 如果是真的 key，**立即撤销** + 重新生成

### F.9 数据库锁定 / 表不存在

**解决**：
```powershell
# 删除数据库重新创建（数据会丢！）
Remove-Item data/book-soul.db -ErrorAction SilentlyContinue
# 重启应用
```

### F.10 端口被占用（8765）

**解决**：
```powershell
# 找占用进程
Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
# 改 .env 里的 BOOK_SOUL_PORT 重启
```

---

## Part G：进度追踪

> 用户可复制这个 checklist 跟踪进度

### Phase 0：环境与基建
- [ ] 0.1 创建 GitHub 仓库
- [ ] 0.2 基础配置文件
- [ ] 0.3 Python 后端初始化
- [ ] 0.4 日志与配置
- [ ] 0.5 LLM 抽象层
- [ ] 0.6 数据库初始化
- [ ] 0.7 Tauri 桌面壳
- [ ] 0.8 质量门禁
- [ ] 0.9 GitHub Actions CI
- [ ] 0.10 Hello World 验证

### Phase 1：核心后端服务
- [ ] 1.1 作品 CRUD
- [ ] 1.2 人物卡 CRUD ⭐
- [ ] 1.3 章节 CRUD + 版本
- [ ] 1.4 大纲 CRUD
- [ ] 1.5 灵感库 CRUD
- [ ] 1.6 加密服务
- [ ] 1.7 记忆系统骨架

### Phase 2：桌面壳 + 前端骨架
- [ ] 2.1 路由与基础布局
- [ ] 2.2 shadcn/ui 集成
- [ ] 2.3 Tauri ↔ Python 通信
- [ ] 2.4 设置页基础
- [ ] 2.5 Zustand 状态管理

### Phase 3：灵感园 - 开新书
- [ ] 3.1 题材选择 + 词库
- [ ] 3.2 灵感词操作
- [ ] 3.3 简要剧情生成
- [ ] 3.4 完整版大纲生成
- [ ] 3.5 人物卡自动生成 ⭐
- [ ] 3.6 人物卡管理 UI
- [ ] 3.7 状态机实现
- [ ] 3.8 保存导出

### Phase 4：创作
- [ ] 4.1 作品选择
- [ ] 4.2 Tiptap 集成
- [ ] 4.3 章节生成（流式）
- [ ] 4.4 选区 AI 重写
- [ ] 4.5 提示词框
- [ ] 4.6 版本控制
- [ ] 4.7 导出 md/word

### Phase 5：质量检测
- [ ] 5.1 检测范围选择
- [ ] 5.2 多维度并行评分
- [ ] 5.3 人设一致性
- [ ] 5.4 题材合规性
- [ ] 5.5 报告 UI

### Phase 6：仓库
- [ ] 6.1 灵感库
- [ ] 6.2 藏书馆
- [ ] 6.3 本地文件夹扫描 ⭐
- [ ] 6.4 Skill 系统基础

### Phase 7：优化与 Skill 完善
- [ ] 7.1 剩余 9 个 Skill
- [ ] 7.2 Skill 市场 UI
- [ ] 7.3 错误处理
- [ ] 7.4 备份恢复

### Phase 8：打包与发布
- [ ] 8.1 Tauri 打包配置
- [ ] 8.2 自动 Release
- [ ] 8.3 文档完善

---

## Part H：开发节奏建议

按 1-2 小时/天 vibe coding：

- **每天 1 个模块**（约 100-200 行代码）
- **每周 5 个模块**
- **8-10 周完成全部**

**不要赶进度**：
- 每个模块完成后**先在 UI 验证**，再开下一个
- 遇到问题**先解决**，不要跳过
- 每周回顾一次进度，调整计划

---

## Part I：紧急情况处理

### I.1 误提交了 API Key

1. **立即**在 provider 撤销
2. 生成新 Key
3. 在 git 历史中清除（见 F.8）
4. 通知 GitHub（如果是公开仓库）

### I.2 数据丢失

- 默认未加密，数据在 `~/Documents/BookSoul/`
- 如果应用卸载但数据还在：直接重新安装应用
- 如果数据目录被删：除非有备份，否则**无法恢复**

### I.3 应用无法启动

```powershell
# 1. 删数据库（先备份！）
Copy-Item data/book-soul.db data/book-soul.db.bak
Remove-Item data/book-soul.db

# 2. 重装依赖
cd server && uv sync
cd ../apps/desktop && pnpm install

# 3. 重启
cd ../.. && pnpm tauri dev
```

### I.4 想完全重置

```powershell
# ⚠️ 删前确保你已有备份！
Remove-Item -Recurse -Force data/
Remove-Item -Recurse -Force apps/desktop/src-tauri/target
Remove-Item -Recurse -Force apps/desktop/node_modules
Remove-Item -Recurse -Force server/.venv
# 然后重新装环境
```

---

## 总结：用户 vs agent 责任清单

### 用户负责
- ✅ 装环境（Part A）
- ✅ 申请 API Key（Part B）
- ✅ 准备素材（Part C）
- ✅ 按对话模板提问（Part D）
- ✅ 跑用户验证清单（Part E）
- ✅ 跟踪进度（Part G）
- ✅ 紧急情况处理（Part I）

### agent 负责
- ✅ 写代码（按 PROJECT_PLAN.md）
- ✅ 写测试
- ✅ 跑 ruff + pytest + pre-commit
- ✅ 配置 CI
- ✅ 给用户验证清单
- ✅ 给 commit 消息建议

### 共同负责
- 进度回顾
- 计划调整
- Bug 修复
