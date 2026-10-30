# Book Soul API 参考

> 后端基于 FastAPI（async）+ SQLAlchemy 2.0（async）+ aiosqlite
> 默认端口 `127.0.0.1:8765`，所有路径以 `/` 开头

## 通用约定

- 错误响应：`{"detail": "..."}` + HTTP 状态码
  - `400` 参数错（业务校验）
  - `404` 资源不存在
  - `422` Pydantic 校验失败 / 业务前置条件不满足
  - `500` 内部错误（LLM 失败等）
  - `501` 端点未启用
- 时间格式：ISO 8601（UTC）
- ID：自增整数

---

## Novels

### `GET /novels`
列出作品。

Query: `?genre=修仙&status=draft&limit=100&offset=0`

Response: `[Novel, ...]`

### `POST /novels`
创建作品。

Body:
```json
{"name": "凡人修仙传", "genre": "xiuxian", "description": "..."}
```

### `GET /novels/{id}`
详情。

### `PATCH /novels/{id}`
部分更新。

### `DELETE /novels/{id}`
删除（幂等）。

---

## Chapters

### `GET /novels/{id}/chapters`
列出某作品章节。`?status=drafting&limit=100&offset=0`

### `POST /novels/{id}/chapters`
创建章节。Body 同 `ChapterCreate`，可附 `content`（自动写 user_create 版本）。

### `GET /chapters/{id}` / `PATCH` / `DELETE`

### `POST /chapters/{id}/content`
写新版本（手动编辑后保存）。Body:
```json
{
  "content": "正文",
  "trigger": "user_edit",
  "prompt": null,
  "metadata": null
}
```

### `GET /chapters/{id}/versions`
版本历史（按时间倒序）。

### `GET /chapters/{id}/versions/{vid}`
单个版本。

### `POST /chapters/{id}/generate`
流式生成章节（**ndjson**）：
- 增量：`{"text": "..."}`
- 完成：`{"done": true, "provider": "...", "model": "..."}`
- 错误：`{"error": "..."}`

Body: `{"user_prompt": "...", "target_word_count": 4000}`

### `POST /chapters/{id}/rewrite`
流式选区/全文重写（**ndjson**）。Body:
```json
{
  "original_text": "原选区",
  "user_prompt": "更紧凑",
  "from_pos": 0,
  "to_pos": 100
}
```

### `GET /chapters/{id}/versions/{vid}/diff?other_id=xx`
返回 unified diff。`other_id` 缺省则与 parent 比。

### `POST /chapters/{id}/versions/{vid}/rollback`
软回滚：把目标版本内容设为当前内容，生成新版本（parent=当前最新）。

Response: `{"new_version": ChapterVersion, "rolled_back_to": int}`

---

## Characters

### `GET /novels/{id}/characters`
列出人物卡。

### `POST /novels/{id}/characters`
创建人物卡。

### `PATCH /characters/{id}` / `DELETE`

### `POST /novels/{id}/characters/generate`
两阶段生成：
1. 抽取：从大纲抽人物列表
2. 生成：逐个生成完整卡

### `POST /novels/{id}/characters/generate-from-outline`
**从已生成的大纲**抽取并生成人物卡（非流式）。

### `POST /novels/{id}/characters/generate-from-outline/stream`
流式从大纲生成人物卡（NDJSON）。

| 事件 | 字段 | 说明 |
|---|---|---|
| `thinking` | `index`, `text` | 思考内容（净身后纯中文） |
| `delta` | `index`, `text` | 人物卡正文增量 |
| `card` | `index`, `character` | 某张卡完成（已落库） |
| `error` | `index`, `message` | 某张卡失败 |
| `done` | `provider`, `model`, `elapsed_sec` | 全部完成 |

> **并行 LLM 调用 + 串行写库**：卡片是并发生成的，但**入库必须串行**
> （`asyncio.Lock`）—— `AsyncSession` 不是并发安全的，并发 `flush()` 会抛
> `Session is already flushing`。

---

## Outlines

### 大纲模式（`outline_type`）

| 取值 | 含义 | structure 形状 |
|------|------|----------------|
| `complete` | 完整大纲：从开头写到全书结束（适合短篇小说） | `{ volumes: [{name, summary, chapters:[{title, summary, key_events}]}], overall_theme }` |
| `semi_open` | 半开放式：只写前期并留悬念，后续由作者自行创作或 AI 辅助续写 | 同上 + `suspense_hook`（悬念钩子） |
| `freedom` | 创作型：散文 + 关键节拍 + 主题 | `{ summary, key_beats: [...], themes: [...] }` |

### `GET /novels/{id}/outlines?outline_type=complete`
列出大纲。

### `POST /novels/{id}/outlines`
创建。

### `POST /novels/outlines/generate`
基于剧情生成大纲（自动建 novel + 大纲）。

Body:
```json
{
  "genre": "修仙",
  "plot_summary": "...",
  "keywords": ["废柴", "逆袭"],
  "novel_name": "凡人修仙传",
  "outline_type": "complete"
}
```

### `POST /novels/outlines/generate/stream`
流式生成大纲（NDJSON）。

事件协议（2026-10-25 改版，2026-10-29 补两阶段细化事件）：

| 事件 | 载荷 | 说明 |
|------|------|------|
| `start` | `phase`, `outline_type` | 开始 |
| `thinking` | `text` | 模型思考中（推理模型的内容，**不丢**） |
| `skeleton` | `structure` | **阶段一**：卷章骨架生成完成 |
| `volume_start` | `index`, `name` | **阶段二**：某卷开始补细节 |
| `volume_done` | `index`, `name` | 某卷补细节完成 |
| `partial` | `structure`, `chapters_done` | **已解析好的**部分大纲结构（卷 → 章 → 关键事件） |
| `structure_ready` | `structure` | 全部卷细化完成 |
| `done` | `novel_id`, `outline_id`, `structure`, `provider`, `model`, `elapsed_sec`, `first_delta_sec` | 完成（含耗时统计） |
| `error` | `message` | 失败 |

> ⚠️ 2026-10-25 之前还有 `delta` 事件（LLM 吐的**原始 JSON** 文本）。
> 现在不再发送 —— 前端拿到 `delta` 只会渲染出一堆 JSON 代码。
> `partial` 里的 `structure` 已经是解析结果，直接渲染即可。

> **两阶段细化**：阶段一只出卷章骨架，阶段二**并行**补每卷的章节详情
> （`summary` + `key_events`），所以章节不再只有标题。
> 阶段二有**调用预算上限**（`MAX_CALLS_PER_VOLUME = 24`）：超预算的章节
> 给占位概要（诚实标注「【待细化】」，不编剧情）。

### `POST /novels/{id}/outlines/{outline_id}/continue/stream`
AI 辅助续写大纲（NDJSON；新增卷追加到原大纲末尾）。

---

## Inspirations

### `GET /inspirations?novel_id=xx&type=keyword&tag=热门`
列出灵感。

### `POST /inspirations`
创建。

### `GET /inspirations/{id}` / `PATCH` / `DELETE`

### `GET /inspirations/{id}/detail`
**Phase 6.1**：返回灵感详情 + 关联作品的人物卡 / 大纲 / 章节摘要。

### `POST /inspirations/generate-plot`
生成 n 个剧情版本（不入库）。

### `POST /inspirations/generate-plot/stream`
流式生成剧情版本（NDJSON）。

Body: `{"genre": "xuanhuan", "keywords": ["剑修"], "n_versions": 3, "user_extra": ""}`

| 事件 | 字段 | 说明 |
|---|---|---|
| `version_start` | `index` | 某版本开始（1-based） |
| `thinking` | `index`, `text` | 模型思考内容（**已净身，纯中文**，不丢内容） |
| `delta` | `index`, `text` | 正文增量 |
| `version_done` | `index`, `summary` | 某版本完成 |
| `error` | `index`, `message` | **单个版本**失败（不影响其他版本） |
| `done` | `provider`, `model`, `elapsed_sec`, `first_delta_sec` | 全部完成 |

> **保序语义**：内容事件（thinking / delta）按到达顺序**实时**透传；
> 只有里程碑事件（`version_done` / `error`）按下标保序。
> 失败的版本同样参与保序（到达终态就让指针前进），不会卡住后续版本。

### `POST /inspirations/reorder`
手动排序（拖动 / 批量管理用）。

Body: `{"ids": [3, 1, 2]}` —— 按数组顺序写 `sort_order`。

> 未出现在列表里的条目会按原相对次序**推到后面**（不会因为 `sort_order=0` 跳到最前）。

### `POST /inspirations/batch-delete`
批量删除。Body: `{"ids": [1, 2, 3]}`

---

## Quality（Phase 5）

### `POST /novels/{id}/chapters/{cid}/quality`
5 维度并行评分。返回 `QualityReport`（总分 + 维度分 + issues + suggestions）。

### `POST /novels/{id}/chapters/{cid}/quality/stream`
流式质检（NDJSON），逐维度出分。

---

## Scanner（Phase 6.3）

### `POST /scanner/scan`
扫描目录。Body: `{"path": "D:/novels", "max_depth": 3}`

Response: `{"novels": [DetectedNovel, ...]}`

### `POST /scanner/import`
导入。Body: `{"dir_path": "...", "genre": "xiuxian"}`

Response: `{"novel_id": int, "name": "...", "chapter_count": int}`

---

## Export（Phase 4.7）

### `GET /novels/{id}/export?format=md|html|docx`
多格式导出。返回 JSON: `{"filename", "mime", "content_b64"}`。

---

## Skills（Phase 6.4+）

### `GET /skills`
列出所有已注册 skill。

### `POST /skills/{name}/run`
执行。Body 为 skill 的 input 字段（任意）。返回 `{"success", "data", "error"}`。

### 已注册的 12 个 skill

| name | input |
|------|-------|
| word_counter | `{"text": "..."}` |
| sensitive_word | `{"text": "...", "words": ["..."]}` |
| chapter_summarizer | `{"text": "...", "head_chars": 200, "tail_chars": 200}` |
| character_extractor | `{"text": "...", "top_n": 10}` |
| plot_analyzer | `{"text": "..."}` |
| web_search | `{"query": "..."}` (当前失败，需配 API) |
| read_local_file | `{"path": "/abs/path.md"}` |
| consistency_checker | `{"text": "..."}` |
| style_analyzer | `{"text": "..."}` |
| pacing_visualizer | `{"text": "..."}` |
| outline_structurer | `{"text": "..."}` |
| genre_classifier | `{"text": "...", "top_n": 3}` |

---

## Backup（Phase 7.4）

### `GET /backup/export`
导出 data_dir 为 .zip（base64 包装）。Response: `{"filename", "mime", "content_b64"}`

### `POST /backup/import`
从 .zip 恢复。Body: `{"zip_b64": "...", "overwrite": true}`

Response: `{"files": int, "manifest_present": bool, "db_backed_up": bool}`

---

## LLM

### `GET /llm/health?provider=xx`
Provider 健康检查（**必须带 API Key** —— `/models` 端点需鉴权，否则无法区分
"服务挂了"和"key 错了"）。

- 结果走 `core/llm/cache.py`：健康 **60s** / 模型清单 **300s** TTL + stale-while-revalidate
- 过期时**先返回旧值再后台刷新** —— 前端永远不等网络
- 改 key / 换 provider 后由 `services/settings_service.py` 作废缓存
- `provider` 可省略（检查全部）

### `GET /llm/models?provider=xx&refresh=1`
列出该 provider 可用模型。`refresh=1` 绕过缓存（设置页「刷新列表」用）。

### `POST /llm/test`
测试连通性。Body: `{"provider": "minimax", "model": "..."}`

---

## WordBanks（种子库，按板块分开管理）

> 板块（genre）互不相通 —— 修仙的词不会出现在都市板块里。

### `GET /wordbanks`
列出所有板块。Response: `{"genres": [{"id", "name", "count", ...}]}`

### `GET /wordbanks/{genre}`
列出该板块的词（按分类）。

### `GET /wordbanks/{genre}/all-words`
返回该板块**全部**词 + 分类列表（种子库管理弹窗用）。

Response: `{"categories": [...], "words": {...}}`

### `POST /wordbanks/{genre}/words`
添加一个新词。Body: `{"category": "themes", "word": "新词"}`

### `PATCH /wordbanks/{genre}/words`
修改一个词。Body: `{"category": "themes", "word": "旧词", "new_word": "新词"}`

### `DELETE /wordbanks/{genre}/words`
删除一个词。Body: `{"category": "themes", "word": "要删的词"}`

### `POST /wordbanks/{genre}/import`
批量导入（JSON）。Body:
`{"items": [{"word": "...", "category": "themes"}], "default_category": "themes"}`

- `default_category` 必须是该板块**实际存在**的分类，否则 **422**（带可用分类列表）
- 返回 `{"imported": int, "skipped": int, "errors": [...]}`

### `POST /wordbanks/{genre}/import-file`
导入文件（原始 body 上传，**multipart**，字段名 `file`）。

---

## Settings

### `GET /settings` / `PATCH /settings`
读取/更新配置（LLM provider / API key / 主题 / 加密 / 数据目录）。

### `DELETE /settings/api-key/{provider}`
清除指定 provider 的 key。

---

## Main

### `GET /ping`
健康检查。`{"ping": "pong"}`
