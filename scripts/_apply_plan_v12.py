"""临时脚本：PROJECT_PLAN.md v1.1 -> v1.2（灵感园三步流程重构）。

用后可删。运行：python scripts/_apply_plan_v12.py
"""

from pathlib import Path

p = Path(__file__).resolve().parents[1] / "PROJECT_PLAN.md"
with p.open("r", encoding="utf-8", newline="") as f:
    text = f.read()
orig = text

# ---------- A. Phase 3 节重写（3.1-3.4 部分） ----------
START = "### Phase 3：灵感园 - 开新书（2 周）"
END = "#### 模块 3.5：人物卡自动生成 ⭐ 核心"
assert text.count(START) == 1, "start marker"
assert text.count(END) == 1, "end marker"
i = text.index(START)
j = text.index(END)

new_a = """### Phase 3：灵感园 - 开新书（2 周）

> 🔄 **v1.2 修订（2026-09-04，提议来源：用户主动）——灵感园三步流程重构**
> - **原因**：原设计把所有步骤与可选卡片挤在同一页（题材、灵感词、剧情、大纲纵向堆叠），视觉混乱、操作不舒适。
> - **新设计**：点开灵感园先看到**三个步骤入口**（灵感词选择 / 简要剧情生成 / 大纲生成），每步单独一页，**只显示本步相关的可选卡片**；每步结果保存为卡片后，用户自选"留在本步重选重生成"或"进入下一步"。
> - **影响范围**：模块 3.1-3.4 重新定义（原 3.1+3.2 合并为新 3.1；原 3.3 → 新 3.2；原 3.4 → 新 3.3；新增 3.4 流程骨架），模块 3.7 状态机同步更新，Part G 进度清单同步。**后端 API / 词库 / prompt / service 全部复用，不受影响**；生成仍为阻塞式（本次不改，流式留待 Phase 4 统一考虑）。
> - **已完成部分**：原 3.1-3.4 的后端 + 配置已在 commit `e14981a` 落地（该 commit 消息为 "Phase 2.6: 灵感园 + 词库 + 题材（部分）"，编号与计划书错位，以此说明为准）。剩余工作以前端三步拆分为主。

#### 新交互流程总览

```
灵感园首页（三个步骤入口卡片）
├─ 第一步 灵感词选择（题材 + 词库合并）
│    选题材 → 抽灵感词 → 刷新/锁定/多选/手动添加
│    → 【保存关键词卡片】
│    → 保存后二选一：① 留在本步，刷新重选创建新卡片
│                     ② 进入第二步
├─ 第二步 简要剧情生成（只显示【关键词卡片】可选）
│    选关键词卡片 → 生成 3 个剧情 → 【保存剧情卡片】
│    → 保存后二选一：① 返回重选关键词卡片重新生成
│                     ② 进入第三步
└─ 第三步 大纲生成（只显示【剧情卡片】可选）
     选剧情卡片（种子）→ 生成大纲（complete / freedom 保留）
     → 自动建作品 + 大纲入库；可返回第二步换剧情卡片
```

**流程原则**：
1. 每一步只展示本步的可选卡片：第一步 = 题材 + 词库；第二步 = 关键词卡片；第三步 = 剧情卡片。
2. 三个步骤**保留原有全部自定义功能**（刷新/锁定/多选/全选/反选/手动添加/提示词框/作品名/大纲 mode 等）。
3. 步骤间数据流统一走灵感库卡片（`/inspirations`，type=keyword / plot），刷新应用不丢。
4. 前置不足时入口置灰 + 空状态提示（如第二步无关键词卡片 → 引导回第一步）。

#### 模块 3.1：灵感词选择步（题材 + 词库 + 保存关键词卡片）

> 由原 3.1（题材选择 + 词库系统）与原 3.2（灵感词生成/刷新/锁定）合并而成。

- **文件**：
  - `config/genres/{xiuxian,dushi,xuanyi,yanqing}.yaml` ✅ 已完成
  - `config/wordbanks/{xiuxian,dushi,xuanyi,yanqing}.yaml` ✅ 已完成
  - `server/src/services/wordbank_service.py` ✅ 已完成
  - `apps/desktop/src/pages/Inspiration/GenreSelect.tsx` ✅ 已完成（待并入步骤页）
  - `apps/desktop/src/pages/Inspiration/KeywordBoard.tsx` ✅ 已完成（待并入步骤页）
- **题材优先级**（JEE 决策，v1.1 确认）：修仙 P0 → 都市 P1 → 悬疑 P2 → 言情 P3（4 题材词库均已落地）
- **词库 YAML 结构**（以修仙 P0 为例）：
  ```yaml
  name: 修仙
  themes: [修炼, 突破, 灵气, 丹药, 法宝, 飞升, 心魔, 渡劫, ...]
  characters: [主角, 师父, 反派, 道侣, 师妹, 长老, ...]
  plots: [退婚, 打脸, 夺宝, 复仇, 升级, 秘境, 宗门大比, ...]
  scenes: [宗门, 拍卖会, 战斗, 遗迹, 秘境, 洞府, ...]
  items: [飞剑, 玉佩, 灵草, 秘籍, 灵兽, 储物袋, ...]
  ```
- **题材顺序配置**（前端用，控制选择顺序）：
  ```typescript
  // apps/desktop/src/config/genres.ts
  export const GENRE_PRIORITY = [
    { id: 'xiuxian', name: '修仙', tier: 'P0', emoji: '🗡️' },
    { id: 'dushi', name: '都市', tier: 'P1', emoji: '🏙️' },
    { id: 'xuanyi', name: '悬疑', tier: 'P2', emoji: '🔍' },
    { id: 'yanqing', name: '言情', tier: 'P3', emoji: '💕' },
  ] as const;
  ```
- **本步交互**：
  - 选题材 → 抽灵感词；刷新 / 锁定 / 多选 / 全选 / 反选 / 手动添加 / 提示词框（全部保留）
  - 确定词语 → **保存为关键词卡片**（`POST /inspirations`，type=keyword）
  - 保存后：① 留在本步刷新重选、创建新卡片；② 进入第二步
- **用户人工**：第一步选"修仙" → 选词 → 保存卡片 → 卡片出现在"我的灵感"

#### 模块 3.2：简要剧情生成步（输入 = 关键词卡片）

> 原 3.3；页面改为只显示关键词卡片可选。

- **文件**：
  - `config/prompts/plot_generation.yaml` ✅ 已完成
  - `server/src/services/inspiration_service.py`（PlotService）✅ 已完成
  - `apps/desktop/src/pages/Inspiration/PlotGenerator.tsx`（待改造为步骤页）
- **生成逻辑**（已实现；v1.2 备注已并行化，3 版本约 96s → 34s）：
  ```python
  async def generate(self, genre: str, keywords: list[str], n_versions: int = 3) -> list[str]:
      \"\"\"并行生成 n 个简要剧情版本\"\"\"
  ```
- **本步交互**：
  - 只显示已保存的【关键词卡片】（多选）作为输入
  - 生成 3 个剧情 → 逐个保存为剧情卡片（type=plot）
  - 保存后：① 返回重选关键词卡片、重新生成；② 进入第三步
- **用户人工**：选关键词卡片 → 生成 3 剧情 → 保存 → 进入下一步

#### 模块 3.3：大纲生成步（输入 = 剧情卡片）

> 原 3.4；页面改为只显示剧情卡片可选。

- **文件**：
  - `config/prompts/outline_complete.yaml` / `outline_freedom.yaml` ✅ 已完成
  - `server/src/services/outline_generator.py` ✅ 已完成
  - `apps/desktop/src/pages/Inspiration/OutlineGenerator.tsx`（待改造为步骤页）
- **输出结构**（LLM 输出 JSON，schema 已落地）：
  ```json
  {
    "volumes": [
      {
        "name": "第一卷 初入修仙",
        "summary": "...",
        "chapters": [
          {"title": "第一章 偶得传承", "summary": "...", "key_events": ["..."]}
        ]
      }
    ]
  }
  ```
- **本步交互**：
  - 只显示已保存的【剧情卡片】（单选，作为大纲种子）
  - complete（分卷/章）/ freedom（散文+节拍）两种 mode 保留；作品名自定义保留（留空用"{genre}新作"）
  - 生成后自动建作品 + 大纲入库；可返回第二步换剧情卡片重生成
- **用户人工**：选剧情卡片 → 选 mode → 生成大纲 → "我的灵感"查看

#### 模块 3.4：三步流程骨架与导航（v1.2 新增）

- **文件**：
  - `apps/desktop/src/pages/Inspiration/index.tsx`（重构：单页堆叠 → 步骤容器）
  - `apps/desktop/src/pages/Inspiration/StepNav.tsx`（新增：三步入口/导航组件）
- **功能**：
  - 灵感园首页显示三个步骤入口卡片；点击进入对应步骤页
  - 步骤间切换用子路由或视图状态；跨步选中状态由 Zustand store（或步骤容器）持有
  - 前置校验：无关键词卡片 → 第二步置灰；无剧情卡片 → 第三步置灰（空状态引导回上一步）
  - "我的灵感"卡片点开可"用作输入"直达对应步骤
- **验收**：任一时刻页面只出现一个步骤的可选卡片；三步来回切换不丢已选内容

"""

text = text[:i] + new_a + text[j:]

# ---------- B. 3.7 状态机状态更新 ----------
old_b = '''class NewBookStateMachine:
      STATES = [
          "idle", "select_genre", "generate_keywords", "select_keywords",
          "generate_plot", "edit_plot", "select_outline_mode",
          "generate_outline", "edit_outline", "generate_characters",
          "edit_characters", "save", "done"
      ]

      TRANSITIONS = {
          "idle": ["select_genre"],
          "select_genre": ["generate_keywords"],
          "generate_keywords": ["select_keywords"],
          "select_keywords": ["generate_plot"],
          # ...
      }'''
new_b = '''class NewBookStateMachine:
      # v1.2：状态与"三步分页流程"对齐（原 select_genre / generate_keywords 等
      # 细粒度状态改为按步骤页组织）
      STATES = [
          "idle", "keyword_step", "plot_step", "outline_step",
          "character_step", "edit_characters", "save", "done",
      ]

      TRANSITIONS = {
          "idle": ["keyword_step"],
          "keyword_step": ["plot_step"],                  # 保存关键词卡片后
          "plot_step": ["keyword_step", "outline_step"],  # 可回上步重选 / 进入大纲
          "outline_step": ["plot_step", "character_step"],
          "character_step": ["edit_characters", "save"],
          "edit_characters": ["character_step", "save"],
          "save": ["done", "keyword_step"],               # 结束或再开一本
      }'''
assert text.count(old_b) == 1, "state machine block"
text = text.replace(old_b, new_b)

# ---------- C. 阶段 3 产出物 ----------
old_c = """#### 阶段 3 产出物

- [ ] 可在 UI 完成"开新书"全流程
- [ ] 灵感词可刷新/锁定
- [ ] 剧情批量生成
- [ ] 大纲生成（两种 mode）
- [ ] 人物卡自动生成 + 人工调整
- [ ] 保存到灵感库
- [ ] 导出 md"""
new_c = """#### 阶段 3 产出物

- [ ] 灵感园首页三步入口清晰，单页不再堆叠所有步骤与卡片
- [ ] 第一步：题材 + 词库合并，关键词可保存为卡片
- [ ] 第二步：仅关键词卡片可选，剧情可保存为卡片
- [ ] 第三步：仅剧情卡片可选，大纲两种 mode 可用
- [ ] 三步均保留自定义功能（刷新/锁定/多选/手动添加/提示词框）
- [ ] 人物卡自动生成 + 人工调整
- [ ] 保存到灵感库
- [ ] 导出 md"""
assert text.count(old_c) == 1, "stage 3 outputs"
text = text.replace(old_c, new_c)

# ---------- D. 文档头版本 + 修订记录 ----------
old_d = """> 文档版本 v1.1 · 2026-09-02
> 项目代号：Book Soul
> 工作目录：`C:\\Users\\JZ\\Desktop\\Book Soul`"""
old_d = old_d.replace("\\\\", "\\")
new_d = """> 文档版本 v1.2 · 2026-09-04
> 项目代号：Book Soul
> 工作目录：`C:\\Users\\JZ\\Desktop\\Book Soul`
>
> **修订记录**：
> - **v1.2（2026-09-04）灵感园三步流程重构**（提议来源：用户主动）。原因：原 Phase 3
>   把所有步骤与可选卡片挤在同一页，操作混乱；目标：简化页面、分割步骤、操作简洁舒适。
>   影响范围：Phase 3 模块 3.1-3.4 重新定义（原 3.1+3.2 合并为新 3.1，原 3.3 → 新 3.2，
>   原 3.4 → 新 3.3，新增 3.4 流程骨架），模块 3.7 状态机与 Part G 进度清单同步；
>   后端 API / 词库 / prompt / service 全部复用。详见 Phase 3 节首的修订说明。
> - v1.1（2026-09-02）：初始确认版（题材优先级、辅助模型 1M 上下文、模型警告机制）。"""
new_d = new_d.replace("\\\\", "\\")
assert text.count(old_d) == 1, "header version"
text = text.replace(old_d, new_d)

# ---------- E. 两处功能表中的灵感园描述 ----------
old_e1 = "| **灵感园** | 选题材 → 抽灵感词 → 生成剧情 → 生成大纲 → 生成人物卡 → 保存 |"
new_e1 = "| **灵感园** | 三步流程：灵感词选择（题材+词）→ 剧情生成 → 大纲生成；每步可保存卡片复用 |"
assert text.count(old_e1) == 1, "table e1"
text = text.replace(old_e1, new_e1)

old_e2 = "| **灵感园** | 开新书（题材→灵感词→剧情→大纲→人物卡）+ 续写 |"
new_e2 = "| **灵感园** | 开新书（三步流程：灵感词→剧情→大纲→人物卡）+ 续写 |"
assert text.count(old_e2) == 1, "table e2"
text = text.replace(old_e2, new_e2)

# ---------- F. Part G 进度清单 Phase 3 ----------
old_f = """### Phase 3：灵感园 - 开新书
- [ ] 3.1 题材选择 + 词库
- [ ] 3.2 灵感词操作
- [ ] 3.3 简要剧情生成
- [ ] 3.4 完整版大纲生成
- [ ] 3.5 人物卡自动生成 ⭐
- [ ] 3.6 人物卡管理 UI
- [ ] 3.7 状态机实现
- [ ] 3.8 保存导出"""
new_f = """### Phase 3：灵感园 - 开新书（v1.2 三步流程）
- [ ] 3.1 灵感词选择步（题材+词库+保存关键词卡片）
- [ ] 3.2 简要剧情生成步（关键词卡片输入）
- [ ] 3.3 大纲生成步（剧情卡片输入）
- [ ] 3.4 三步流程骨架与导航
- [ ] 3.5 人物卡自动生成 ⭐
- [ ] 3.6 人物卡管理 UI
- [ ] 3.7 状态机实现
- [ ] 3.8 保存导出"""
assert text.count(old_f) == 1, "part G checklist"
text = text.replace(old_f, new_f)

with p.open("w", encoding="utf-8", newline="") as f:
    f.write(text)
print("OK, all edits applied. size:", len(orig), "->", len(text))
