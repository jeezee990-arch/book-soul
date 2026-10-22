"""统一日志配置（基于 loguru）。

约定：
- 控制台输出：带颜色，简洁
- 文件输出：JSON 格式，便于后续分析（位于 ``<data_dir>/logs/server.log``）
- 日志等级从 :class:`Settings.log_level` 读取
- 拦截标准 :mod:`logging`（uvicorn / sqlalchemy / fastapi 都会走这里）
- 同一进程内多次调用 :func:`setup_logging` 是幂等的
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

from .config import settings

_CONFIGURED = False


def _resolve_level(level: str) -> str:
    """把环境变量值规范化成 loguru 接受的形式（大写）。"""
    return level.strip().upper() if level.strip() else "INFO"


def setup_logging(*, level: str | None = None) -> None:
    """初始化日志。

    应在应用启动的最早期调用（在 ``Settings`` 实例化之后）。
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = _resolve_level(level or settings.log_level)
    log_dir: Path = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "server.log"

    # 0) 移除 loguru **默认 handler**（它也写 stderr）。
    #    不移除的话每条日志会被输出两遍（默认 handler + 我们自己的 sink），
    #    打包成 sidecar 后尤其明显（stderr 被重定向到文件，文件里全是重复行）。
    logger.remove()

    # 1) 控制台 sink：带颜色的简洁输出。
    #    ⚠️ PyInstaller 打包成 `console=False`（GUI 子系统）后，
    #    如果父进程没有重定向标准流，`sys.stderr` 可能是 None。
    #    这时 loguru.add(None) 会抛异常 → 整个后端起不来。
    #    所以这里判空跳过控制台 sink —— 文件 sink（server.log）永远可用。
    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
    else:
        logger.warning("stderr 不可用（GUI 子系统模式），仅输出到文件")

    # 2) 文件 sink：带轮转
    logger.add(
        log_file.as_posix(),
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        enqueue=True,
    )

    # 3) 拦截标准 logging（uvicorn / sqlalchemy / fastapi 等）
    _intercept_std_logging(log_level)

    _CONFIGURED = True
    logger.info("Logging initialized: level={}, file={}", log_level, log_file)


def _intercept_std_logging(level: str) -> None:
    """把 :mod:`logging` 的所有记录桥接到 loguru。"""

    class _InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level_no = logger.level(record.levelname).name
            except ValueError:
                level_no = record.levelno
            frame, depth = logging.currentframe(), 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back  # type: ignore[assignment]
                depth += 1
            logger.opt(depth=depth, exception=record.exc_info).log(level_no, record.getMessage())

    logging.root.handlers = [_InterceptHandler()]
    logging.root.setLevel(level)

    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        std_logger = logging.getLogger(noisy)
        std_logger.handlers = [_InterceptHandler()]
        std_logger.propagate = False


def get_logger():
    """对外暴露的 logger（业务代码 ``from src.core.logging import get_logger``）。"""
    return logger
