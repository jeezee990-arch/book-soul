# Book Soul 启动指南 + 人工验证清单

> 对应版本：0.1.1（2026-11）
> 面向：第一次从源码运行，或发布前做人工验收的人

---

## 一、怎么启动？三选一

### 方式 A：独立版（推荐，最像"独立软件"）

**你需要做什么**：双击一个 exe。

```
<仓库根>\dist\Book Soul\Book Soul.exe
```

- **不需要**装 Python / Node / Rust
- **不需要**开终端，**不会**弹出黑色控制台窗口
- **不需要**配环境变量（API Key 可以在软件"设置"页里填）
- 数据存在 `dist\Book Soul\data\`，**整个文件夹拷到别的地方照样能用**（便携模式）

如果 `dist\Book Soul\` 还不存在，先构建一次：

```powershell
cd "<仓库根>"
powershell -ExecutionPolicy Bypass -File scripts\build_standalone.ps1
```

> 首次构建约 5-8 分钟（Rust release 编译最慢）；之后约 1-2 分钟。

### 方式 B：安装包

构建时会同时产出 NSIS 安装包：

```
apps\desktop\src-tauri\target\release\bundle\nsis\Book Soul_<版本>_x64-setup.exe
```

双击安装 → 开始菜单和桌面会出现 "Book Soul" 图标 → 点图标启动。
安装模式是 **currentUser**（装到你的用户目录，不写 `Program Files`，避免只读导致数据写不进去）。

### 方式 C：开发模式（改代码时用）

```powershell
cd "<仓库根>"
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

带可见控制台，能看后端日志。前端热更新。

### 装桌面快捷方式（一次性）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1
```

脚本会**优先指向独立版 exe**；没有独立版时才回退到开发模式启动器。
想强制重指：`install_shortcut.ps1 -Force`

---

## 二、人工验证清单

> 每一步都写清楚了**要打开什么软件**、**看什么**、**怎么算通过**。

### ✅ 第 1 步：独立版能不能起来（最重要）

**打开什么**：文件资源管理器 → `<仓库根>\dist\Book Soul\` → 双击 `Book Soul.exe`

**看什么**：
1. 屏幕上出现一个标题为 **Book Soul** 的窗口（1400×900）
2. 窗口中央短暂显示"正在启动写作引擎…"（转圈），1-5 秒后进入**写作**页面
3. **不应该**弹出任何黑色控制台窗口

**怎么算通过**：看到了写作页三栏布局 —— 左边章节树 / 中间纸面编辑区 / 右边上下文面板

**如果失败**：画面会显示"写作引擎启动失败"，并附带**具体原因**（比如"找不到后端可执行文件"）。
去这里看详细日志：

```
dist\Book Soul\data\logs\desktop.log     ← 桌面端启动日志（失败原因在这）
dist\Book Soul\data\logs\server.log      ← 后端业务日志
dist\Book Soul\data\logs\backend.log     ← 后端进程原始输出
```

> 用记事本打开 `desktop.log` 能正常显示中文（文件带 UTF-8 BOM）。

---

### ✅ 第 2 步：数据确实存在应用目录里（便携模式）

**打开什么**：文件资源管理器 → `dist\Book Soul\data\`

**看什么**：应该有

```
data\
├── book-soul.db          ← SQLite 数据库（你的小说、人物卡都在这）
├── logs\                 ← 三个日志文件
└── skills\               ← 用户自定义 skill 的存放位置
```

**怎么算通过**：`book-soul.db` 存在，且文件大小在增长

**反证测试**：把整个 `dist\Book Soul\` 文件夹复制到桌面（比如 `<桌面>\BS\`），
双击那里的 `Book Soul.exe` —— 依然能用，数据写在**新位置**的 `data\` 里。
这证明它真的不依赖仓库、不依赖注册表。

---

### ✅ 第 3 步：API Key 能不能用（最关键的功能验证）

**前置**：你已经用环境变量配过 Key（`config/llm.yaml` 里对应 provider 的环境变量名）。

**打开什么**：Book Soul 软件 → 左侧导航 → **设置** 页

**看什么**：
1. provider 列表里应该有"可用 / 不可用"的状态标记
2. `mimo` 和 `minimax` 应该是**可用**（之前实测过这两个通）
3. `openai` 应该是不可用（没配 Key）
4. `ollama` 应该是不可用（本地没跑 Ollama）

**怎么算通过**：至少一个 provider 显示可用

**如果想改用"设置页填 Key"**（打包版没有 `.env` 的情况下）：
设置页填入 Key → 保存 → 重启软件 → 确认状态变成"可用"。

**安全检查**：去 `dist\Book Soul\data\secrets\keys.json` 看一眼 ——
文件里应该是 **DPAPI 加密后的乱码**，**绝不能**出现明文 Key。

---

### ✅ 第 4 步：流式输出是不是真的"一个字一个字出来"（这是你报的那个 bug）

**打开什么**：Book Soul → 左侧导航 → **开新书** → 第 1 步「种子」

**操作**：
1. 在「**书名**」输入框里填一个名字（比如「剑起青云」）。填素材库里**已有的**名字时，
   输入框下方会提示「素材库里已有同名作品《X》，保存时会自动改为《X 2》」
2. 选一个题材（比如"修仙"）
3. 在候选词里点几个关键词（也可以直接输入，回车即加入）
4. 点 **「生成 3 个剧情」** → 进第 2 步「剧情」，三个走向同时流式出来
5. 选中一个 → 进第 3 步「大纲与人物」，等它显示「作品骨架已就绪」
6. 走完后去**素材库 → 作品**：应该能看到这本书，名字是**你填的名字**
   （不填就是程序自动命名的），且**旧书的大纲没被覆盖**

**看什么**：
- 三个版本框应该**同时开始出字**，字符是**一个一个冒出来**的
- **不应该**是等好几秒后"啪"一下全出来

**怎么算通过**：能看到文字在持续、逐段增长

**要更精确地测量**：打开 `data\logs\server.log`，找 `delta` 相关的日志行，
看第一条和最后一条的时间戳差 —— 这就是流式真实的持续时间。

> **为什么以前是"跟阻塞一样"**：`httpx` 的 `client.post()` 会先把整个响应 body 读完
> 才返回，等于把流式退化成了阻塞。现在改用 `client.stream()`，并且有契约测试
> （`server/tests/test_llm_streaming_contract.py`）锁住这个行为，改回去测试立刻变红。

**顺手验证一下"慢"的问题**：同样的操作再跑一次，注意从点按钮到第一个字出现的时间。
正常应该 **≤ 3 秒**。如果超过 10 秒，看 `server.log` 里有没有 provider 超时。

---

### ✅ 第 5 步：全流程能不能走通

**操作**（开新书）：
1. 生成 3 个剧情 → 点选一个 → 自动生成大纲与人物卡
2. 等提示"大纲与人物卡都已入库，可以直接开始写第一章"
3. 到**写作页**新建一章 → 点生成 → 看章节正文流式出来

**看什么**：每一步都能走到下一步，没有卡死、没有报错弹窗

---

### ✅ 第 6 步：素材库能不能管理作品（重命名 / 排序 / 删除）

**打开什么**：Book Soul → 左侧导航 → **素材库** → **作品** Tab

**操作**：
1. 在任意一张作品卡上**右键**（或点卡片右上角的 **「⋯」**）→ 应该弹出菜单：
   继续写 / 重命名 / 上移 / 下移 / 导出 Markdown·HTML·Word / 删除
2. 点「**重命名**」→ 输入框里应该**预填当前书名** → 改成新名字 → 保存
3. 再右键另一本 → 点「**上移**」→ 列表顺序应该真的变了，右下角提示「已移动」
4. 右上角「**排序**」下拉切换成「最近更新 / 字数最多 / 按书名」→ 顺序应该跟着变
5. 再点「**删除**」→ 弹出二次确认（写明会连同章节、人物卡、大纲一起删）→ 确认

**看什么**：
- 菜单能弹出，9 个项目齐全
- 已经在第一本的「上移」、最后一本的「下移」是**置灰**的
- 重命名后列表上的名字立刻变
- 删除后列表少一本，计数（右上角「共 N 部」）同步减

**怎么算通过**：上面 5 步都能在界面上看到对应变化

**重名怎么验**：把书名改成素材库里**已经有的**另一个名字 → 保存 → 应该弹出
「已有同名作品 / 素材库里已经有《X》，换个名字吧」，**原名不变**。

> ⚠️ 素材库里**同一时间只能有一本同名作品**（去首尾空白后精确比较）。
> 「开新书」和「导入」撞名会自动加序号（X → X 2），「新建作品」和「重命名」撞名会被拦下来。

---

### ✅ 第 7 步：关闭软件后不留残余进程

**打开什么**：任务管理器（Ctrl + Shift + Esc）

**操作**：
1. 打开 Book Soul，确认任务管理器里出现 `Book Soul.exe` **和** `book-soul-server.exe`
2. 关闭 Book Soul 窗口
3. 再看任务管理器

**看什么**：两个进程都**消失**了

**怎么算通过**：没有残留的 `book-soul-server.exe`

> 这背后有两层保护：① Rust 侧在窗口关闭 / 进程退出时主动 kill 子进程；
> ② Python 侧有**父进程看门狗**（`core/watchdog.py`），主程序被强杀时后端自己退出。
> 就算你在任务管理器里直接"结束任务"强杀 Book Soul，后端也会在 2 秒内自己退掉。

---

### ✅ 第 8 步：装完不装卸载

**打开什么**：文件资源管理器 → `dist\Book Soul\`

**看什么**：文件列表应该是

```
Book Soul.exe          ← 主程序（双击这个）
book-soul-server.exe   ← 后端（主程序自动拉起，不用手动点）
data\                  ← 数据目录
README.txt             ← 简短说明
```

**怎么算通过**：**只有** `Book Soul.exe` 是入口；`book-soul-server.exe` 不该被用户手动双击

---

### ✅ 第 9 步：正文排版与字数对不对（2026-10-30 新增）

**打开什么**：Book Soul → **写作** → 选一章有正文的章节

**看什么**：
1. 正文**有段落**（不是一整块挤成一行），段落之间有空行
2. 汉字之间**没有多余空格**（「他 走 到」应该是「他走到」）
3. **不同人物的对话分行**，能看清谁在说话
   （`“甲？”“乙。”` 应该是两段；`将“沈”“砚”二字` 里的引用**不该**被拆）
4. 界面上提示的字数 = 目标字数 ±10%（目标 3600 → 3240 ~ 3960）

**怎么交叉验证**：
- 点「导出 Word」，在 Word 里用「审阅 → 字数」看统计 —— **应该和界面一致**
- 目标 3600 字时，Word 里也应该在 3240 ~ 3960 之间

> **为什么以前对不上**：旧版把每个流式批次写成一个段落，正文里塞满空行，
> 字数又用 `len(text)` 把换行和空格全算进去 —— 界面显示 5338 字，
> Word 里实际只有 3309 字，差 61%。现已修复。

**老章节怎么办**：修复前生成的章节用脚本重排段落
```powershell
# 1) 假段落 → 重新断段
& .\.venv\Scripts\python.exe scripts\repair_chapter_paragraphs.py `
    --data-dir "<仓库根>\dist\Book Soul\data"

# 2) 段落划分不动，只拆挤在一起的连续对白
& .\.venv\Scripts\python.exe scripts\repair_chapter_paragraphs.py `
    --data-dir "<仓库根>\dist\Book Soul\data" --split-dialogue
```
会**新建一个版本**，原版本保留在版本历史里，随时可回滚。加 `--dry-run` 先看不写库。

---

## 三、命令速查

```powershell
# 构建独立版（产物在 dist\Book Soul\）
powershell -ExecutionPolicy Bypass -File scripts\build_standalone.ps1

# 开发模式启动（带控制台日志）
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# 零控制台启动（优先独立版，没有则开发模式）
wscript.exe scripts\launcher.vbs

# 装 / 卸桌面快捷方式
powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1
powershell -ExecutionPolicy Bypass -File scripts\uninstall_shortcut.ps1

# 后端测试（781 个用例）
cd server; uv run pytest -q --cov=src --cov-report=term

# 前端测试（275 个用例）
cd apps\desktop; pnpm test

# Rust 检查
cd apps\desktop\src-tauri; cargo check
```

---

## 四、已知限制

| 限制 | 说明 |
|---|---|
| 打包版**没有** `.env` | API Key 只能来自环境变量或设置页（DPAPI 加密存储） |
| 首次启动 PyInstaller 解包约 2-4 秒 | 属于 PyInstaller onefile 的固有开销；实测总启动在 5 秒内 |
| Rust release 编译慢 | 首次 `pnpm tauri build` 约 3 分钟，之后走缓存 |
| NSIS 安装包和便携版**并存** | 装过安装包再用便携版时，两边的 `data\` 是独立的 |
| 前端测试只覆盖纯逻辑 | DOM 交互（状态机跳转、diff 渲染）还没自动化测试 |
