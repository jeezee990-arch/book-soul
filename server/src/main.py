"""Book Soul 后端服务入口。

启动方式（在 ``server/`` 目录下）：
    uv run python -m src.main

或者（项目根目录）：
    uv run --directory server python -m src.main
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .api import router as api_router
from .core.config import settings
from .core.logging import setup_logging
from .core.skills.loader import init_skill_paths, load_all_skills
from .core.watchdog import start_parent_watchdog
from .db import init_db

# 应用启动最早阶段初始化日志（必须在任何业务 logger.info 之前调用）
setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：DB 同步装载 + skills 后台异步装载，关闭时记录日志。

    性能优化（Phase 性能优化）：
    - DB init 在 startup 同步跑（必须先建表才能 serve 请求）
    - Skill loading 在 background task 异步跑（~600-1000ms）——
      首 LLM 请求到达时若仍未完成，会短暂等待 loading 完成
    """
    logger.info(
        "Starting Book Soul server (host={}, port={})",
        settings.book_soul_host,
        settings.book_soul_port,
    )

    await init_db()

    skills_root = settings.data_dir / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    init_skill_paths(skills_root)

    # ⚠️ 用**普通守护线程**而不是 ``asyncio.to_thread``：
    #    to_thread 会把结果挂到 event loop 的 future 上。技能加载要跑几百毫秒，
    #    如果 app 停得比它快（测试里很常见），线程结束时就会往**已关闭**的
    #    loop 上投递回调 → 线程里抛 "Event loop is closed"（pytest 会报成
    #    PytestUnhandledThreadExceptionWarning）。
    #    普通线程 + Event 就没有这个耦合。
    skills_ready = threading.Event()
    threading.Thread(
        target=_load_skills_threaded,
        args=(skills_ready,),
        name="book-soul-skills-load",
        daemon=True,
    ).start()

    # provider 预检放后台：不能拖慢启动（探活每个 provider 最多 5s）
    preflight_task = asyncio.create_task(
        _preflight_providers(),
        name="book-soul-provider-preflight",
    )

    try:
        yield
    finally:
        # 等技能加载完（最多 2 秒）—— 只是为了让关服日志里有 "Skills loaded: N"
        for _ in range(40):
            if skills_ready.is_set():
                break
            await asyncio.sleep(0.05)
        if not preflight_task.done():
            preflight_task.cancel()
        logger.info("Shutting down Book Soul server")


def _load_skills_threaded(ready: threading.Event) -> None:
    """在后台线程里加载所有 skill，完成后置位 ``ready``。

    单独抽出来是为了让线程体尽量短 —— 异常也要兜住，
    不能让线程静默死掉（``ready`` 永远不置位，关服时要多等 2 秒）。
    """
    try:
        load_all_skills()
    except Exception as e:  # noqa: BLE001
        logger.warning("skill loading failed: {}", e)
    finally:
        ready.set()


async def _preflight_providers() -> None:
    """启动预检：探测各 provider 可达性，不可用只告警不阻塞启动。

    背景：配置里多个场景默认路由到本地 Ollama，而 Ollama 经常"没启动"。
    与其让用户等 30 秒超时后看到裸 ConnectError，不如启动时就明确告知。

    ⚠️ 必须走 ``llm_cache.get_health()``，**不能**直接调
    ``check_all_providers_health()``：

    - 走 cache 才能和前端启动时那次 ``GET /llm/health`` **共用同一个探测任务**。
      直调的话两边各打一轮外部网络 —— 前端启动那一下要白等一整轮探测
      （实测 2.7s），而且同一个 provider 被探测两次。
    - ``get_health()`` 内部会把结果写进缓存，所以顶栏模型灯随后是 0 延迟命中。
    """
    from .core.llm import cache as llm_cache

    try:
        results = await llm_cache.get_health()
    except Exception as e:  # noqa: BLE001
        logger.warning("provider preflight failed: {}", e)
        return
    for name, (ok, message) in results.items():
        if ok:
            logger.info("provider '{}' OK — {}", name, message)
        else:
            logger.warning("provider '{}' UNAVAILABLE — {}", name, message)


app = FastAPI(
    title="Book Soul",
    description="AI 辅助小说写作桌面应用 - 后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

# 实际绑定的端口（serve() 会用真实值覆盖）。
# 桌面版由 Tauri 分配随机端口，配置里的 8765 并不是真实端口 ——
# /ping 必须回报真实值，否则排查问题时会被误导。
app.state.actual_port = settings.book_soul_port

# CORS：dev 模式 Vite (5173) 与后端 (8765) 跨 origin；prod 模式 Tauri webview
# 不走 http(s) 协议，但保险起见也允许 tauri:// / http://tauri.localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "tauri://localhost",
        "http://tauri.localhost",
        # Tauri 2 + WebView2 on Windows uses these origins
        "https://tauri.localhost",
        "http://0.0.0.0:8765",
        "null",  # file:// origin (Tauri fallback)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# 挂载 API 路由
app.include_router(api_router)


def serve(host: str | None = None, port: int | None = None) -> None:
    """启动 uvicorn（dev 与打包版共用）。

    :param host: 监听地址（None → settings.book_soul_host）
    :param port: 监听端口（None → settings.book_soul_port）
    """
    import sys

    import uvicorn

    # 性能优化（Phase 性能优化）：
    # - http="httptools"：用 httptools 解析 HTTP，比默认快 ~20%
    # - loop="uvloop"：Linux/macOS 用 uvloop 替换 asyncio（Windows 不支持，自动回退）
    # - backlog=2048：高并发连接堆积
    # - timeout_keep_alive=30：客户端空闲保持连接时长
    kwargs: dict[str, object] = {
        "host": host or settings.book_soul_host,
        "port": port if port is not None else settings.book_soul_port,
        "reload": False,
        "http": "httptools",
        "backlog": 2048,
        "timeout_keep_alive": 30,
        "log_level": "info",
    }
    # 记录真实端口（/ping 用它回报，别让调用方被配置里的默认端口误导）
    app.state.actual_port = int(kwargs["port"])
    # uvloop 在 Windows 上 import 即报错；只在非 Windows 才启用
    if sys.platform != "win32":
        try:
            import uvloop  # type: ignore[import-not-found]  # noqa: F401

            kwargs["loop"] = "uvloop"
        except ImportError:
            pass

    # ⚠️ 传 app 对象（不是 "src.main:app" 字符串）：
    #    打包后不存在可重新 import 的 src.main 模块，字符串形式会 RuntimeError。
    uvicorn.run(app, **kwargs)


def run_from_cli(argv: list[str] | None = None) -> None:
    """解析命令行参数并启动服务。

    dev（``python -m src.main``）和打包版（``run_server.py``）**共用**这一份
    参数定义 —— 之前两边各写一套 argparse，打包版漏了 ``--parent-pid``，
    结果桌面端传过去的参数会被 argparse 当成"无法识别的参数"直接报错退出。

    :param argv: 参数列表（None → 取 sys.argv[1:]，便于测试）
    """
    import argparse

    parser = argparse.ArgumentParser(prog="book-soul-server", description="Book Soul backend")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="监听端口（默认取 settings.book_soul_port）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="监听地址（默认取 settings.book_soul_host）",
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="父进程 pid；桌面端传入，父进程消失时后端自动退出",
    )
    # ⚠️ 必须把 argv 传进去：parse_args() 不带参数时读的是 sys.argv[1:]，
    #    在测试里那会变成 pytest 的参数 → argparse 直接 SystemExit(2)。
    args = parser.parse_args(argv)

    # 看门狗要在 uvicorn 占用主线程**之前**启动
    start_parent_watchdog(args.parent_pid)

    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    run_from_cli()
