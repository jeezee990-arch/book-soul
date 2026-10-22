# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec —— 把 Book Soul 后端打成单文件 exe（Tauri sidecar）。

用法（从 ``server/`` 目录）
--------------------------
    uv run pyinstaller book_soul.spec --noconfirm

产物
----
    server/dist/book-soul-server.exe

再由 ``scripts/build_sidecar.ps1`` 复制到
``apps/desktop/src-tauri/binaries/book-soul-server-<target-triple>.exe``，
Tauri 打包时自动带上。

⚠️ 三条硬性约束
---------------
1. **入口用 ``run_server.py``**（绝对 import）——``src/main.py`` 的相对 import
   在 ``__main__`` 下会失败
2. **``config/`` 必须作为数据打进去**——提示词 / 题材 / 词库是运行时依赖
3. **``.env` 绝不能打进去**——里面有 API Key
"""

from pathlib import Path

# SPECPATH = spec 文件所在目录（server/）
SERVER_DIR = Path(SPECPATH).resolve()
ROOT = SERVER_DIR.parent

# ===== 数据文件 =====
datas = [
    # 整个 config/ 目录：llm.yaml / app.yaml / prompts/ / genres/ / wordbanks/ / skills/
    (str(ROOT / "config"), "config"),
]

# ===== 动态 import 的库 =====
# PyInstaller 靠静态分析找依赖，以下都是"运行时才 import"的，必须显式列出
hiddenimports = [
    # uvicorn 的协议/loop/lifespan 是按字符串动态加载的
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # SQLAlchemy 异步 SQLite
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "aiosqlite",
    # cryptography（Fernet / DPAPI 依赖 openssl 扩展）
    "cryptography.hazmat.primitives.ciphers.algorithms",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.backends.openssl.backend",
    # keyring（Windows 凭据管理器）
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.win32",
    "keyring.backends.chainer",
    # 其他
    "yaml",
    "httpx",
    "httpx._transports.default",
    "httpcore",
    "anyio",
    "loguru",
    "pydantic",
    "pydantic.deprecated.decorator",
    "email_validator",
    "docx",
    "docx.opc.constants",
]

block_cipher = None

a = Analysis(
    [str(SERVER_DIR / "run_server.py")],
    pathex=[str(SERVER_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 减体积：这些在桌面场景用不到
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "IPython",
        "notebook",
        "pytest",
        "alembic",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="book-soul-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # 控制台窗口：GUI 应用启动后不应该再弹一个黑色控制台
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
