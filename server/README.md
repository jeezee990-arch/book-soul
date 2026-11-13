# Book Soul Server

FastAPI + SQLAlchemy（async）后端服务。

## 启动

```bash
# 在仓库根执行：根 pyproject.toml 是 uv workspace，venv 统一落在仓库根 .venv
uv sync --all-packages --extra dev

cd server
uv run python -m src.main
```

服务启动后：

- Swagger UI：<http://127.0.0.1:8765/docs>
- 健康检查：<http://127.0.0.1:8765/ping>

> 开发模式建议用 `scripts/dev.ps1` 启动：它会设置 `BOOK_SOUL_DATA_DIR=data/dev`，
> 并让 Tauri 与后端共用同一套端口 / 数据目录约定。

## 测试与检查

```bash
cd server
uv run pytest -q --cov=src --cov-report=term-missing
uv run ruff check .
uv run mypy src/core src/services
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BOOK_SOUL_HOST` | `127.0.0.1` | 监听地址 |
| `BOOK_SOUL_PORT` | `8765` | 监听端口；打包版由 Rust 侧传入随机端口 |
| `BOOK_SOUL_DATA_DIR` | `~/Documents/BookSoul/` | 数据目录（数据库 / 密钥 / 日志） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

API Key 见仓库根 `.env.example` 与 `config/llm.yaml` 的 `api_key_env`。

## 相关文档

- [API 参考](../docs/API.md)
- [架构设计](../docs/ARCHITECTURE.md)
