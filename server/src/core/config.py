"""全局配置加载器（pydantic-settings）。

约定：
- 必填字段（LLM Key 等）从 .env 读取
- 服务端口、数据目录等有默认值，可被 .env 覆盖
- 业务代码统一用 ``from src.core.config import settings`` 获取
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 数据目录 =====
    # 留空时回落到用户文档目录下的 BookSoul/
    book_soul_data_dir: Path | None = Field(default=None, alias="BOOK_SOUL_DATA_DIR")

    # ===== 服务 =====
    book_soul_host: str = Field(default="127.0.0.1", alias="BOOK_SOUL_HOST")
    book_soul_port: int = Field(default=8765, alias="BOOK_SOUL_PORT")

    # ===== 日志 =====
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ===== 加密（可选）=====
    encryption_enabled: bool = Field(default=False, alias="ENCRYPTION_ENABLED")

    # ===== LLM（minimax 主用）=====
    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_base_url: str = Field(
        default="https://api.minimaxi.com/v1", alias="MINIMAX_BASE_URL"
    )

    # ===== LLM（OpenAI 备用）=====
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )

    # ===== LLM（Ollama 本地）=====
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1", alias="OLLAMA_BASE_URL"
    )

    @property
    def data_dir(self) -> Path:
        """解析后的数据目录（永远返回一个有效路径）。"""
        if self.book_soul_data_dir is not None and str(self.book_soul_data_dir).strip():
            return Path(self.book_soul_data_dir).expanduser().resolve()
        return (Path.home() / "Documents" / "BookSoul").resolve()

    @property
    def db_path(self) -> Path:
        """SQLite 数据库文件路径。"""
        return self.data_dir / "book-soul.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局唯一配置实例（首次实例化后缓存）。"""
    return Settings()


# 便捷访问：业务代码可直接 ``from src.core.config import settings``
settings = get_settings()
logger.info(
    "Config loaded: data_dir={}, host={}, port={}, log_level={}",
    settings.data_dir,
    settings.book_soul_host,
    settings.book_soul_port,
    settings.log_level,
)
