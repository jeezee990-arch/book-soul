# Skills 自动调用系统（Phase Skills 自动化）

> Skill **不需要手动调用**——它预装后会自动注入到对应的业务场景。

## 两种来源

| 来源 | 位置 | 加载时机 |
|---|---|---|
| **内置** | `server/src/core/skills/builtin/*.py` | 后端启动 |
| **用户预装** | `<data_dir>/skills/<name>/manifest.yaml` + `handler.py` | 后端启动 |

`<data_dir>` 由 `BOOK_SOUL_DATA_DIR` 环境变量决定；开发模式默认 `data/dev/skills/`。

## 预装一个 Skill

```bash
# 1. 复制模板
cp -r config/skill_template data/dev/skills/my_skill

# 2. 编辑 manifest.yaml：写 name / triggers / type
# 3. 编辑 handler.py：实现 create_skill() -> Skill
# 4. 重启后端（启动器会读最新 skills/）
```

最简 `handler.py` 示例：

```python
from ...base import Skill, SkillResult

class MySkill:
    name = "my_skill"
    description = "..."
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}
    requires_llm = False

    async def execute(self, *, text: str = "", **_):
        return SkillResult(success=True, data={"text": text.upper()})

def create_skill():
    return MySkill()
```

## 触发规则

`manifest.yaml` 的 `triggers` 决定哪些 scene 会自动调用它：

```yaml
triggers:
  - all                        # 所有场景
  - scene:plot_generation      # 剧情生成完成后
  - scene:outline_generation   # 大纲生成完成后
  - scene:character_generation # 人物卡生成后
  - scene:chapter_generation   # 章节正文生成后
  - scene:chapter_rewrite      # 章节重写后
  - scene:quality_check        # 质量检测
  - scene:summary              # 摘要
```

## `type`（执行时机）

| 取值 | 含义 |
|---|---|
| `post_process` | LLM 流式输出**完成后**自动调用（默认） |
| `pre_process` | LLM 调用**之前**注入到 system prompt |
| `both` | 两者都做 |

## 调用约定

后端在以下场景自动调用 `apply_post(scene, text)`：

| 场景 | 触发位置 |
|---|---|
| `plot_generation` | 剧情生成的每个 `version_done` 之前 |
| `outline_generation` | 大纲 JSON 解析之前（注意：skill 不能破坏 JSON 结构） |
| `character_generation` | 人物卡 YAML 解析之前（同样要 YAML-safe） |
| `chapter_generation` | PATCH `/chapters/{id}/content` 保存时（trigger=llm_generate / rewrite） |

每个 skill 的 `execute()` 接收 `text: str` 参数，返回 `SkillResult`：
- `success=True, data={"text": "..."}` → 用新文本继续后续处理
- `success=False` 或抛出异常 → 保留原文本，日志记录警告

## 启停

Web UI → **Skills 页面**：右侧开关切换启停。

REST API：

```bash
GET    /skills                  # 列出（含 source / enabled / triggers）
GET    /skills/scene/{scene}    # 某 scene 当前自动调用的 skill 名
POST   /skills/{name}/enable    # 启用
POST   /skills/{name}/disable   # 禁用
POST   /skills/{name}/run       # debug：手动执行（一般不需要）
```

## 内置 Skill 默认触发表

| Skill | 触发 | 默认 |
|---|---|---|
| `sensitive_word` | `all` | ✅ 开 |
| `word_counter` | `all` | ✅ 开 |
| `chapter_summarizer` | `scene:chapter_generation` | ✅ 开 |
| `style_analyzer` | chapter 生成 / 重写 / 剧情 | ❌ 关 |
| `consistency_checker` | chapter 生成 / 重写 | ❌ 关 |
| `pacing_visualizer` | chapter 生成 | ❌ 关 |
| `character_extractor` | outline 生成 | ❌ 关 |
| `genre_classifier` | 剧情生成 | ❌ 关 |
| `outline_structurer` | outline 生成 | ❌ 关 |
| `plot_analyzer` | 剧情生成 | ❌ 关 |
| `read_local_file` | `all`（pre） | ❌ 关 |
| `web_search` | `all`（pre） | ❌ 关 |

需要哪个开哪个，去 Skills 页一键启用即可。