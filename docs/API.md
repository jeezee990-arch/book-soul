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

事件协议（2026-10-25 改版）：

| 事件 | 载荷 | 说明 |
|------|------|------|
| `start` | `phase`, `outline_type` | 开始 |
| `thinking` | `text` | 模型思考中（推理模型的内容，**不丢**） |
| `partial` | `structure`, `chapters_done` | **已解析好的**部分大纲结构（卷 → 章 → 关键事件） |
| `done` | `novel_id`, `outline_id`, `structure`, `provider`, `model`, `elapsed_sec`, `first_delta_sec` | 完成（含耗时统计） |
| `error` | `message` | 失败 |

> ⚠️ 2026-10-25 之前还有 `delta` 事件（LLM 吐的**原始 JSON** 文本）。
> 现在不再发送 —— 前端拿到 `delta` 只会渲染出一堆 JSON 代码。
> `partial` 里的 `structure` 已经是解析结果，直接渲染即可。

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

---

## Quality（Phase 5）

### `POST /novels/{id}/chapters/{cid}/quality`
5 维度并行评分。返回 `QualityReport`（总分 + 维度分 + issues + suggestions）。

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

### `GET /llm/providers`
列出配置的 provider。

### `GET /llm/test/{provider}`
测试连通性。

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
