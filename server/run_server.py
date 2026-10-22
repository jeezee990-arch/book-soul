"""PyInstaller 打包入口（薄壳）。

为什么需要单独一个文件
----------------------
PyInstaller 把入口脚本当作 ``__main__`` 执行，而 ``src/main.py`` 内部用的是
**相对 import**（``from .api import router``）。在 ``__main__`` 下相对 import
会直接抛 ``ImportError: attempted relative import with no known parent package``。

所以打包入口用**绝对 import** 把真正的逻辑拉进来。

参数解析不在这里写 —— 统一走 :func:`src.main.run_from_cli`，
这样 dev（``python -m src.main``）和打包版接受**完全一样**的参数，
不会出现"打包版漏了某个参数"的坑。

用法
----
    cd server
    uv run pyinstaller book_soul.spec --noconfirm
"""

from __future__ import annotations

from src.main import run_from_cli


def main() -> None:
    """启动后端（参数解析见 :func:`src.main.run_from_cli`）。"""
    run_from_cli()


if __name__ == "__main__":
    main()
