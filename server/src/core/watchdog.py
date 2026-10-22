"""父进程看门狗：桌面端消失时，后端自行退出。

背景
----
桌面版由 Tauri 拉起 Python 后端子进程。正常情况下窗口关闭 → Rust 侧
``kill_backend()`` 干掉子进程。但有两种情况会留下**孤儿后端**：

1. 用户从任务管理器强杀桌面端（Rust 来不及执行清理）
2. 桌面端自身崩溃

孤儿后端的危害：继续占着端口、继续占着 SQLite 文件锁（导致下次启动打不开库），
而且用户完全不知道它存在 —— 表现为"重启后行为诡异"。

解决方式
--------
桌面端把自己的 pid 通过 ``--parent-pid`` 传给后端。后端起一个守护线程，
每 2 秒检查一次父进程是否还活着；一旦发现父进程没了，就优雅退出。

为什么不能直接用 ``os.kill(pid, 0)``
-------------------------------------
Windows 上 ``os.kill(pid, 0)`` **不是**"检查进程是否存在"，而是
``TerminateProcess(handle, 0)`` —— 它会把那个进程**杀掉**。在 Windows 上
必须走 ``OpenProcess`` + ``GetExitCodeProcess``。
"""

from __future__ import annotations

import os
import sys
import threading

from loguru import logger

# 看门狗轮询间隔（秒）
POLL_INTERVAL_SECS = 2.0

# Windows 上进程"仍在运行"的退出码
_STILL_ACTIVE = 259

# 停止信号：测试和优雅关闭场景需要能停掉看门狗线程
_STOP_EVENT = threading.Event()


def _process_alive_windows(pid: int) -> bool:
    """Windows 版存活检查：``OpenProcess`` + ``GetExitCodeProcess``。

    :param pid: 目标进程 id
    :return: True = 进程还活着；False = 已退出 / 不存在
    """
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover - 非 Windows 平台
        return _process_alive_posix(pid)

    # PROCESS_QUERY_LIMITED_INFORMATION：只查询信息、不干预进程的权限位。
    # 用查询受限信息而不是 PROCESS_ALL_ACCESS，可以避免触发跨权限的访问拒绝。
    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
    if not handle:
        # 打不开：进程不存在（或者权限不足，但同用户进程不会权限不足）
        return False

    exit_code = wintypes.DWORD()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)
    if not ok:
        return False
    return exit_code.value == _STILL_ACTIVE


def _process_alive_posix(pid: int) -> bool:
    """POSIX 版存活检查：``os.kill(pid, 0)``（signal 0 只做权限/存在性检查）。"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在，只是我们没权限发信号
        return True
    except OSError:
        return False
    return True


def process_alive(pid: int) -> bool:
    """跨平台判断进程是否存活。"""
    if sys.platform == "win32":
        return _process_alive_windows(pid)
    return _process_alive_posix(pid)


def start_parent_watchdog(parent_pid: int | None) -> None:
    """启动父进程看门狗（守护线程）。

    :param parent_pid: 父进程 pid；None 或非法值时**什么都不做**
        （dev 模式下后端独立运行，不能因为"没有父进程"就自杀）
    """
    if not parent_pid or parent_pid <= 0:
        logger.debug("未指定 parent-pid，跳过看门狗")
        return

    if parent_pid == os.getpid():
        logger.warning("parent-pid 与自身相同，跳过看门狗")
        return

    _STOP_EVENT.clear()
    logger.info(f"看门狗已启动：监控父进程 pid={parent_pid}")

    def _watch() -> None:
        while not _STOP_EVENT.is_set():
            # 用 Event.wait 而不是 time.sleep —— 收到停止信号能立刻醒来
            if _STOP_EVENT.wait(POLL_INTERVAL_SECS):
                return
            if not process_alive(parent_pid):
                logger.warning(f"父进程 pid={parent_pid} 已退出，后端主动退出")
                # 用 os._exit 而不是 sys.exit：这里是守护线程，
                # sys.exit 只会结束当前线程，后端照样活着。
                os._exit(0)

    thread = threading.Thread(target=_watch, name="book-soul-parent-watchdog", daemon=True)
    thread.start()


def stop_parent_watchdog() -> None:
    """停止看门狗线程（幂等）。

    主要给测试用 —— 看门狗会在父进程消失时调用 ``os._exit(0)``，
    如果测试里启动了真实线程，它可能把整个测试进程干掉（而且退出码是 0，
    看起来像"测试通过"，实际是中途被杀）。
    """
    _STOP_EVENT.set()
