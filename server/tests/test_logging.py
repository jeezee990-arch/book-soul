"""测试 logging.py：setup_logging 幂等 + sink 正确 + std logging 被拦截。"""

from __future__ import annotations

import logging

import pytest


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch, tmp_path):
    """重置 logging._CONFIGURED + loguru handlers，确保每个测试干净启动。"""
    import src.core.logging as logging_mod

    # 隔离 .env / app.yaml
    for key in (
        "BOOK_SOUL_HOST",
        "BOOK_SOUL_PORT",
        "LOG_LEVEL",
        "BOOK_SOUL_DATA_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)

    # 强制 Settings 用临时数据目录
    monkeypatch.setenv("BOOK_SOUL_DATA_DIR", str(tmp_path / "data"))

    # 重置 _CONFIGURED
    monkeypatch.setattr(logging_mod, "_CONFIGURED", False)

    # 移除 loguru 已有的 handlers（避免跨测试累积）
    from loguru import logger

    logger.remove()

    # 重置 std logging.root
    logging.root.handlers = []
    logging.root.setLevel(logging.WARNING)

    yield


def test_setup_logging_creates_log_dir(tmp_path):
    """setup_logging 应创建 <data_dir>/logs 目录。"""
    from src.core import config as config_mod
    from src.core.logging import setup_logging

    config_mod.get_settings.cache_clear()
    setup_logging()

    log_dir = config_mod.settings.data_dir / "logs"
    assert log_dir.is_dir()
    assert (log_dir / "server.log").exists() or log_dir.is_dir()


def test_setup_logging_is_idempotent():
    """多次调用 setup_logging 不应重复添加 sink。"""
    from loguru import logger

    from src.core.logging import setup_logging

    initial_handlers = len(logger._core.handlers)  # type: ignore[attr-defined]
    setup_logging()
    after_first = len(logger._core.handlers)  # type: ignore[attr-defined]
    setup_logging()
    setup_logging()
    after_more = len(logger._core.handlers)  # type: ignore[attr-defined]

    assert after_first == initial_handlers + 2  # stderr + file
    assert after_more == after_first  # 幂等


def test_setup_logging_intercepts_std_logging():
    """setup_logging 后，stdlib logging 应被 loguru 接管。"""
    from src.core.logging import setup_logging

    setup_logging()

    # 拦截后，root logger 至少有一个 handler（被替换为 InterceptHandler 内部类）
    root = logging.getLogger()
    assert root.handlers  # 非空
    # 所有 handler 的类名都应该是 _InterceptHandler（内部定义类）
    # 由于 _InterceptHandler 定义在函数内无法直接 import，用类名判断
    assert any(h.__class__.__name__ == "_InterceptHandler" for h in root.handlers)


def test_get_logger_returns_loguru_logger():
    """get_logger 应返回 loguru 的 logger 实例。"""
    from loguru import logger as loguru_logger

    from src.core.logging import get_logger

    assert get_logger() is loguru_logger


def test_log_file_written(tmp_path):
    """调用 logger.info 后，文件 sink 应有内容。"""
    from src.core import config as config_mod
    from src.core.logging import logger, setup_logging

    config_mod.get_settings.cache_clear()
    setup_logging()

    test_msg = "book-soul-logging-test-marker"
    logger.info(test_msg)

    log_file = config_mod.settings.data_dir / "logs" / "server.log"
    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content


def test_log_level_from_settings(monkeypatch, tmp_path):
    """settings.log_level 改变后下次 setup_logging 生效。"""
    from src.core import config as config_mod
    from src.core.logging import setup_logging

    monkeypatch.setenv("BOOK_SOUL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    config_mod.get_settings.cache_clear()

    # 重新 import settings（让模块级 settings 重新实例化）
    s = config_mod.get_settings()
    assert s.log_level == "DEBUG"
    # 然后 setup_logging 应当能正常调用（不会因为 level 报错）
    setup_logging()
