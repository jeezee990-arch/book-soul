"""PyInstaller 打包入口（薄壳）。

为什么需要单独一个文件
----------------------
PyInstaller 把入口脚本当作 ``__main__`` 执行，而 ``src/main.py`` 内部用的是
**相对 import**（``from .api import router``）。在 ``__main__`` 下相对 import
会直接抛 ``ImportError: attempted relative import with no known parent package``。

所以打包入口用**绝对 import** 把真正��逻辑拉进来。

用法
----
    cd server
    uv run pyinstaller book_soul.spec --noconfirm
"""

from __future__ import annotations

from src.main import serve


def main() -> None:
    """启动后端（参数解析在 :func:`src.main.serve` 上游的 argparse 里）。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="book-soul-server", description="Book Soul backend (packaged)"
    )
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--host", type=str, default=None)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
