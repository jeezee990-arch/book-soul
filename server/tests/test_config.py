"""测试 config.py：Settings 加载 + yaml 合并 + 派生属性。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """每个测试用临时 .env / 临时数据目录隔离，避免污染真实环境。"""
    # 清理关键 env 变量
    for key in (
        "BOOK_SOUL_HOST",
        "BOOK_SOUL_PORT",
        "BOOK_SOUL_DATA_DIR",
        "LOG_LEVEL",
        "ENCRYPTION_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    # 临时 .env
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("PWD", str(tmp_path))  # 仅占位，避免被 .env 读

    # 把 .env 写到当前工作目录（Settings 用 CWD 解析 .env）
    cwd_env = tmp_path / ".env"
    cwd_env.write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    yield


def test_settings_defaults():
    """不设置任何环境变量时，Settings 给出合理默认值。"""
    from src.core.config import Settings

    s = Settings()
    assert s.book_soul_host == "127.0.0.1"
    assert s.book_soul_port == 8765
    assert s.log_level in ("INFO", "DEBUG", "WARNING", "ERROR")
    assert s.encryption_enabled is False
    assert s.minimax_base_url.startswith("https://")


def test_settings_from_env(monkeypatch, tmp_path):
    """通过环境变量覆盖默认值。"""
    monkeypatch.setenv("BOOK_SOUL_PORT", "9999")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENCRYPTION_ENABLED", "true")
    monkeypatch.chdir(tmp_path)  # 隔离 .env

    from src.core.config import Settings

    s = Settings()
    assert s.book_soul_port == 9999
    assert s.log_level == "DEBUG"
    assert s.encryption_enabled is True


def test_data_dir_default():
    """未设置 BOOK_SOUL_DATA_DIR 时回落到 ~/Documents/BookSoul。"""
    from src.core.config import Settings

    s = Settings()
    expected = (Path.home() / "Documents" / "BookSoul").resolve()
    assert s.data_dir == expected


def test_data_dir_from_env(monkeypatch, tmp_path):
    """设置 BOOK_SOUL_DATA_DIR 后使用它。"""
    custom = tmp_path / "my-data"
    monkeypatch.setenv("BOOK_SOUL_DATA_DIR", str(custom))
    monkeypatch.chdir(tmp_path)

    from src.core.config import Settings

    s = Settings()
    assert s.data_dir == custom.resolve()
    assert s.db_path == custom.resolve() / "book-soul.db"


def test_yaml_merge_fills_missing(monkeypatch, tmp_path):
    """config/app.yaml 在 .env 未设的字段上提供值。"""
    # 改用临时 yaml：构造一个项目根的 config/app.yaml
    # 找到真实项目根（server/src/core/config.py 的 parents[3]）
    from src.core import config as config_mod

    real_yaml_finder = config_mod._find_app_yaml

    def fake_finder():
        fake = tmp_path / "app.yaml"
        fake.write_text(
            "version: 1\n"
            "book_soul_host: 0.0.0.0\n"
            "book_soul_port: 7777\n"
            "log_level: WARNING\n",
            encoding="utf-8",
        )
        return fake

    monkeypatch.setattr(config_mod, "_find_app_yaml", fake_finder)
    # 同时清掉 lru_cache，让 get_settings() 重新走一遍
    config_mod.get_settings.cache_clear()

    # 强制 reload config module 的 settings 实例
    s = config_mod.Settings()
    assert s.book_soul_host == "0.0.0.0"
    assert s.book_soul_port == 7777
    assert s.log_level == "WARNING"

    # 恢复
    config_mod._find_app_yaml = real_yaml_finder  # type: ignore[assignment]
    config_mod.get_settings.cache_clear()


def test_yaml_does_not_override_env(monkeypatch, tmp_path):
    """.env 优先级高于 yaml。"""
    from src.core import config as config_mod

    real_yaml_finder = config_mod._find_app_yaml

    def fake_finder():
        fake = tmp_path / "app.yaml"
        fake.write_text(
            "version: 1\n"
            "book_soul_port: 7777\n",
            encoding="utf-8",
        )
        return fake

    monkeypatch.setattr(config_mod, "_find_app_yaml", fake_finder)
    monkeypatch.setenv("BOOK_SOUL_PORT", "8888")
    monkeypatch.chdir(tmp_path)

    s = config_mod.Settings()
    assert s.book_soul_port == 8888  # env 胜出

    config_mod._find_app_yaml = real_yaml_finder  # type: ignore[assignment]
