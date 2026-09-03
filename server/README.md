# Book Soul Server

FastAPI 后端服务。

## 启动

```bash
# 在 server/ 目录下
uv sync
uv run python -m src.main
```

服务启动后：
- Swagger UI：http://127.0.0.1:8765/docs
- 健康检查：http://127.0.0.1:8765/ping

## 端口

默认 `127.0.0.1:8765`，可通过环境变量 `BOOK_SOUL_HOST` / `BOOK_SOUL_PORT` 覆盖。

## 数据目录

默认 `~/Documents/BookSoul/`，可通过 `BOOK_SOUL_DATA_DIR` 覆盖。
SQLite 数据库文件位于数据目录下：`book-soul.db`。
