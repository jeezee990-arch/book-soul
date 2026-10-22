"""父进程看门狗的单元测试。

覆盖要点
--------
1. ``process_alive`` 对自身进程返回 True，对已死进程返回 False
2. ``start_parent_watchdog`` 在参数非法时**不启动线程**（dev 模式不能自杀）
3. ``run_from_cli`` 正确解析 ``--port/--host/--parent-pid`` 并转发给 serve
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading

import pytest

from src.core import watchdog
from src.core.watchdog import process_alive, start_parent_watchdog, stop_parent_watchdog


class TestProcessAlive:
    """存活检测。"""

    def test_current_process_is_alive(self) -> None:
        """自己的进程一定活着。"""
        assert process_alive(os.getpid()) is True

    def test_dead_process_is_not_alive(self) -> None:
        """已退出的子进程不再存活。"""
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait(timeout=10)
        assert process_alive(proc.pid) is False

    def test_nonexistent_pid_is_not_alive(self) -> None:
        """一个几乎不可能被分配的 pid。"""
        assert process_alive(999_999) is False


class TestStartParentWatchdog:
    """看门狗启动条件。"""

    def test_none_pid_starts_no_thread(self) -> None:
        """None → 不启动线程（dev 模式后端独立运行）。"""
        before = threading.active_count()
        start_parent_watchdog(None)
        assert threading.active_count() == before

    def test_zero_pid_starts_no_thread(self) -> None:
        """0 → 不启动线程。"""
        before = threading.active_count()
        start_parent_watchdog(0)
        assert threading.active_count() == before

    def test_negative_pid_starts_no_thread(self) -> None:
        """负数 → 不启动线程。"""
        before = threading.active_count()
        start_parent_watchdog(-1)
        assert threading.active_count() == before

    def test_self_pid_starts_no_thread(self) -> None:
        """parent_pid == 自身 → 不启动（否则会立刻自杀）。"""
        before = threading.active_count()
        start_parent_watchdog(os.getpid())
        assert threading.active_count() == before

    def test_valid_pid_starts_daemon_thread(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """合法 pid → 启动一个守护线程。

        ⚠️ 这里必须把 ``process_alive`` 打成永远 True，并把 ``os._exit`` 换成假实现。
        看门狗在父进程消失时会调用 ``os._exit(0)`` —— 那是**整个进程**退出。
        如果测试里放一个真线程，父进程（跑测试的 shell）一退出，
        pytest 就会被静默杀掉，**退出码还是 0**，看起来像"全过"，
        实际上测试跑到一半就没了（连摘要行都不打印）。
        """
        monkeypatch.setattr(watchdog, "process_alive", lambda pid: True)
        monkeypatch.setattr(watchdog.os, "_exit", lambda code: None)

        before = threading.active_count()
        start_parent_watchdog(os.getppid())
        try:
            names = [t.name for t in threading.enumerate()]
            assert "book-soul-parent-watchdog" in names
            assert threading.active_count() == before + 1
        finally:
            stop_parent_watchdog()

    def test_stop_is_idempotent(self) -> None:
        """重复调用 stop 不会报错。"""
        stop_parent_watchdog()
        stop_parent_watchdog()


class TestWatchdogThread:
    """看门狗线程行为。"""

    def test_thread_dies_when_parent_dies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """父进程"消失"时，看门狗线程应当退出循环。

        这里不真的让进程自杀（会带走 pytest），
        而是断言"检测到父进程没了"这个分支确实被走到。
        """
        exited = threading.Event()

        def _fake_exit(code: int) -> None:
            exited.set()

        monkeypatch.setattr(watchdog.os, "_exit", _fake_exit)
        monkeypatch.setattr(watchdog, "POLL_INTERVAL_SECS", 0.01)
        monkeypatch.setattr(watchdog, "process_alive", lambda pid: False)

        start_parent_watchdog(424242)
        try:
            assert exited.wait(timeout=5), "看门狗没有在父进程消失后触发退出"
        finally:
            stop_parent_watchdog()


class TestRunFromCli:
    """CLI 参数解析（dev 与打包版共用）。"""

    def test_parses_port_host_and_parent_pid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """三个参数都要能解析并转发。"""
        captured: dict[str, object] = {}

        def _fake_serve(host: str | None = None, port: int | None = None) -> None:
            captured["host"] = host
            captured["port"] = port

        monkeypatch.setattr("src.main.serve", _fake_serve)
        monkeypatch.setattr("src.main.start_parent_watchdog", lambda pid: None)

        from src.main import run_from_cli

        run_from_cli(["--port", "4321", "--host", "127.0.0.1", "--parent-pid", "1234"])

        assert captured["port"] == 4321
        assert captured["host"] == "127.0.0.1"

    def test_defaults_are_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """不传参数时 host/port 都是 None（走 settings 默认值）。"""
        captured: dict[str, object] = {}

        def _fake_serve(host: str | None = None, port: int | None = None) -> None:
            captured["host"] = host
            captured["port"] = port

        monkeypatch.setattr("src.main.serve", _fake_serve)
        monkeypatch.setattr("src.main.start_parent_watchdog", lambda pid: None)

        from src.main import run_from_cli

        run_from_cli([])

        assert captured["host"] is None
        assert captured["port"] is None

    def test_parent_pid_reaches_watchdog(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--parent-pid 必须真的传给看门狗（否则孤儿进程问题会复发）。"""
        seen: list[int | None] = []

        monkeypatch.setattr("src.main.serve", lambda host=None, port=None: None)
        monkeypatch.setattr("src.main.start_parent_watchdog", lambda pid: seen.append(pid))

        from src.main import run_from_cli

        run_from_cli(["--parent-pid", "999"])

        assert seen == [999]
