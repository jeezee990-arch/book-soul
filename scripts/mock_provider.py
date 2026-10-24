"""本地 mock LLM provider（给**没有 API Key** 时手动验证 UI 用）。

和 ``scripts/perf_probe.py`` 用的是同一套 mock（那边是拿它做性能测量）。
区别：这里**只起 mock**，不起后端、不打请求，就是让本地后端有个能回话的 provider。

用法
----
::

    # 1) 起 mock（占用 11434）
    python scripts/mock_provider.py

    # 2) 让后端指向它：设置页 → LLM 与密钥 → Provider 选 ollama
    #    模型随便填一个（mock 的 /models 只返回 qwen2.5:14b）
    #    或者写死配置文件：<data_dir>/.book-soul-settings.yaml
    #      llm:
    #        provider: ollama
    #        model: qwen2.5:14b

    # 3) 起后端 + 前端，走一遍「开新书」三步
    #    set BOOK_SOUL_DATA_DIR=<一个临时目录>
    #    cd server; python run_server.py --port 8765
    #    cd apps/desktop; pnpm dev --port 5173

mock 会按请求里的提示词特征返回对应内容（见 ``mock_content.py``）：
剧情吐假字，大纲吐合法 JSON，人物卡吐合法 YAML —— 所以三步都能走通。

环境变量
--------
``MOCK_DELAY_MS``  每个 chunk 的间隔（默认 50）
``MOCK_CHARS``     每个 chunk 多少字（默认 12）
``MOCK_THINK_MS``  模拟"思考"空窗（默认 0）

⚠️ **别和 pytest 同时跑**：mock 占着 11434 端口。
"""

# ruff: noqa: T201  # CLI 工具，stdout 就是它的输出渠道
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perf_probe import MOCK_PORT, start_mock  # noqa: E402


def main() -> None:
    """起 mock 并阻塞（Ctrl+C 退出）。"""
    start_mock()
    print(f"mock LLM provider listening on 127.0.0.1:{MOCK_PORT}", flush=True)
    print("  在设置页把 Provider 选成 ollama，模型填 qwen2.5:14b", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("bye", flush=True)


if __name__ == "__main__":
    main()
