"""全局配置加载器（pydantic-settings）。

约定：
- 必填字段（LLM Key 等）从 .env 读取
- 服务端口、数据目录等有默认值，可被 .env 覆盖
- 用户配置（``config/app.yaml``）作为 .env 未设置时的回退
- 业务代码统一用 ``from src.core.config import settings`` 获取
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_app_yaml() -> Path | None:
    """定位 ``config/app.yaml``。

    顺序：
    1. ``<repo_root>/config/app.yaml``（项目内）
    2. ``<data_dir>/app.yaml``（用户级覆盖，未来支持）
    """
    repo_root = Path(__file__).resolve().parents[3]  # server/src/core/config.py → 根
    candidate = repo_root / "config" / "app.yaml"
    return candidate if candidate.is_file() else None


def _load_yaml_defaults() -> dict:
    """从 ``config/app.yaml`` 读默认值。失败返回空 dict（不阻塞启动）。"""
    yaml_path = _find_app_yaml()
    if yaml_path is None:
        return {}
    try:
        with yaml_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to load app.yaml from {}: {}", yaml_path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    data.pop("version", None)
    return data


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

    def __init__(self, **kwargs: object) -> None:
        """从 ``config/app.yaml`` 注入用户默认值。

        优先级（高 → 低）：.env > app.yaml > 代码默认值。

        注意：pydantic-settings 把 ``init kwargs`` 视为最高优先级，会覆盖 env。
        所以我们不能直接把 yaml 注入到 init kwargs；正确做法是：检查每个字段
        的 env alias，如果 env 已经有值就跳过 yaml，否则才用 yaml 填入。
        """
        yaml_defaults = _load_yaml_defaults()
        for k, v in yaml_defaults.items():
            # 跳过空值（让代码默认值生效）
            if v in (None, ""):
                continue
            field_info = type(self).model_fields.get(k)
            if field_info is None:
                continue
            env_alias = field_info.alias
            if env_alias and os.environ.get(env_alias, ""):
                # env 已显式设置，env 优先
                continue
            # env 未设，用 yaml 填入 init kwargs
            kwargs.setdefault(k, v)
        super().__init__(**kwargs)

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
