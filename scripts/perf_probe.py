"""性能探针：生成慢到底是**模型**的锅还是**我们代码**的锅？

方法
----
起一个本地 mock OpenAI 兼容 SSE provider（吐字节奏**已知**），
把真实后端指过去（provider ``ollama`` → 127.0.0.1:11434），
然后打真实 HTTP 端点，逐行测量 ndjson。

这些数字说明什么
----------------
- TTFB（HTTP 头）        = 有没有被 HTTP 层缓冲
- 第一个事件              = 我们的固定开销
- 每两个 delta 的间隔     = 我们的开销（mock 的间隔是已知的）
- 总耗时                  = mock 的总时长 + 我们的开销

所以：**开销 = 实测间隔 − mock 间隔**。
开销接近 0 → 慢在模型；开销明显 → 慢在代码。

2026-10-24 实测结论：开销 **+0.5ms/token**（40 个 delta，间隔 50.6ms vs mock 的 50ms），
整条流总开销 ~100ms → **流式链路不是瓶颈，慢在模型**。

用法
----
::

    python scripts/perf_probe.py                    # 默认 50ms/chunk
    MOCK_DELAY_MS=20 python scripts/perf_probe.py   # 更快的吐字节奏
    MOCK_THINK_MS=2000 python scripts/perf_probe.py # 模拟 2 秒"思考"空窗
    N_VERSIONS=3 python scripts/perf_probe.py       # 3 个版本并行

⚠️ **别和 pytest 同时跑**：mock 占着 11434 端口，
而 ``test_llm_models_endpoint.py`` 会去探 ollama 端口 → 互相干扰。
"""

# ruff: noqa: T201  # 这是一个 CLI 探针，stdout 就是它的输出渠道
from __future__ import annotations

import itertools
import json
import os
import socket
import statistics
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mock_content import extract_prompt_text, pick_content

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

# ---- knobs -----------------------------------------------------------------
MOCK_PORT = 11434
CHUNK_DELAY_MS = int(os.environ.get("MOCK_DELAY_MS", "50"))
CHUNK_COUNT = int(os.environ.get("MOCK_CHUNKS", "40"))
THINK_MS = int(os.environ.get("MOCK_THINK_MS", "0"))  # 模拟"思考"空窗
CHARS_PER_CHUNK = int(os.environ.get("MOCK_CHARS", "12"))
# 未知场景的兜底内容长度上限。
# 为什么需要：后端 ``plot_summary`` 上限 5000 字，超了下一个接口直接 422。
MAX_FALLBACK_CHARS = int(os.environ.get("MOCK_MAX_CHARS", "4000"))

# 剧情场景的版本轮换计数器（让并行的 3 张剧情卡内容不同，近似真实的多采样）
_VARIANT_COUNTER = itertools.count()

# ---- mock SSE provider -----------------------------------------------------


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:  # 静音
        pass

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": [{"id": "qwen2.5:14b"}]})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}

        if not payload.get("stream"):
            text = "非流式响应。" * 20
            self._json(
                {
                    "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                }
            )
            return

        # ---- SSE 流式 ----
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def write_chunk(payload_bytes: bytes) -> None:
            self.wfile.write(b"%x\r\n" % len(payload_bytes) + payload_bytes + b"\r\n")
            self.wfile.flush()

        # 模拟推理模型的"思考"空窗（<think> 块要闭合，否则后面的正文会被吞）
        if THINK_MS > 0:
            time.sleep(THINK_MS / 1000)
            write_chunk(
                b'data: {"choices":[{"delta":{"content":"<think>\\u6211\\u60f3\\u60f3</think>"}}]}\n\n'
            )

        # 内容按场景选：剧情吐假剧情，大纲/人物卡吐**能被后端解析**的 JSON/YAML
        # （否则大纲那一步会 parse 失败，向导退回第 2 步，UI 走不到第 3 步）。
        #
        # fallback 长度要封顶：未知场景下 ``CHARS_PER_CHUNK * CHUNK_COUNT`` 可能上万，
        # 而后端 ``plot_summary`` 上限 5000 字 —— 超了下一个接口直接 422，
        # 向导会卡在第 3 步。封顶后最坏情况也只是"内容短"，不会"接口报错"。
        fallback = "字" * min(CHARS_PER_CHUNK * CHUNK_COUNT, MAX_FALLBACK_CHARS)
        content = pick_content(
            extract_prompt_text(payload),
            fallback=fallback,
            variant=next(_VARIANT_COUNTER),
        )
        step = max(1, CHARS_PER_CHUNK)
        pieces = [content[i : i + step] for i in range(0, len(content), step)]
        for piece in pieces:
            time.sleep(CHUNK_DELAY_MS / 1000)
            line = json.dumps({"choices": [{"delta": {"content": piece}}]}, ensure_ascii=False)
            write_chunk(f"data: {line}\n\n".encode())

        write_chunk(b"data: [DONE]\n\n")
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


class DualStackServer(ThreadingHTTPServer):
    """同时监听 IPv6 + IPv4。

    为什么必须双栈：``config/llm.yaml`` 里 ollama 的 base_url 是 ``http://localhost:11434``，
    而 Windows 上 ``localhost`` 通常**先解析成 ::1**。如果 mock 只听 127.0.0.1，
    httpx 会先连 ::1（秒失败）再等 **250ms**（happy eyeballs 的间隔）才试 IPv4 ——
    这 250ms 是**测量假象**，不是被测代码的开销。
    """

    address_family = socket.AF_INET6
    daemon_threads = True

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def start_mock() -> ThreadingHTTPServer:
    srv = DualStackServer(("::", MOCK_PORT), MockHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> None:
    import httpx
    import uvicorn

    # 数据目录用临时目录 —— 不能污染仓库，也不能碰到用户真实数据
    tmp_dir = tempfile.mkdtemp(prefix="book-soul-perf-")
    data_dir = Path(tmp_dir)
    os.environ["BOOK_SOUL_DATA_DIR"] = str(data_dir)
    # 选 ollama（base_url = http://127.0.0.1:11434/v1 → 指向 mock）
    (data_dir / ".book-soul-settings.yaml").write_text(
        "llm:\n  provider: ollama\n  model: qwen2.5:14b\n", encoding="utf-8"
    )

    mock = start_mock()
    port = free_port()

    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            httpx.get(f"{base}/ping", timeout=1)
            break
        except Exception:
            time.sleep(0.25)

    print(f"mock SSE provider : 127.0.0.1:{MOCK_PORT}")
    print(f"  chunk delay      : {CHUNK_DELAY_MS} ms")
    print(f"  chunks           : {CHUNK_COUNT} x {CHARS_PER_CHUNK} chars")
    print(f"  think gap        : {THINK_MS} ms")
    print(f"backend            : {base}")
    print()

    body = {
        "genre": "修仙",
        "keywords": ["逆袭", "宗门", "打脸"],
        "n_versions": int(os.environ.get("N_VERSIONS", "3")),
        "user_extra": "",
    }
    t0 = time.perf_counter()
    stamps: list[tuple[float, dict]] = []
    with httpx.Client(timeout=300) as client:
        with client.stream("POST", f"{base}/inspirations/generate-plot/stream", json=body) as resp:
            print(f"HTTP status        : {resp.status_code}")
            print(f"TTFB (headers)     : {(time.perf_counter() - t0) * 1000:.0f} ms")
            for line in resp.iter_lines():
                if not line:
                    continue
                stamps.append((time.perf_counter() - t0, json.loads(line)))

    total = time.perf_counter() - t0
    print()
    print(f"events received    : {len(stamps)}")
    print(f"total wall time    : {total * 1000:.0f} ms")
    if stamps:
        print(f"first event at     : {stamps[0][0] * 1000:.0f} ms")
        first_delta = next((s[0] for s in stamps if s[1].get("event") == "delta"), float("nan"))
        print(f"first DELTA at     : {first_delta * 1000:.0f} ms")

        # 只看**第一个版本**的 delta 间隔：
        # 其它版本的 delta 在队列里排着（有序合并），会被一口气吐出来，
        # 间隔全是 0，混进来会把统计搅乱。
        dts = [s[0] for s in stamps if s[1].get("event") == "delta" and s[1].get("index") == 1]
        gaps = [round((b - a) * 1000, 1) for a, b in zip(dts, dts[1:], strict=False)]
        if gaps:
            print(f"v1 delta count     : {len(dts)}")
            print(f"v1 delta gap median: {statistics.median(gaps):.1f} ms")
            print(f"v1 delta gap min/max: {min(gaps):.1f} / {max(gaps):.1f} ms")
            print(f"expected gap (mock): {CHUNK_DELAY_MS} ms")
            print(
                f"==> CODE OVERHEAD  : {statistics.median(gaps) - CHUNK_DELAY_MS:+.1f} ms per delta"
            )
        order = [
            s[1].get("event")
            for s in stamps
            if s[1].get("event") in ("version_start", "version_done")
        ]
        print(f"event order        : {order}")
        idx_seq = [s[1].get("index") for s in stamps if s[1].get("event") == "delta"]
        groups: list[int] = []
        for i in idx_seq:
            if not groups or groups[-1] != i:
                groups.append(i)
        print(f"delta group order  : {groups}   (expect 1,2,3 = A,B,C in order)")

    server.should_exit = True
    mock.shutdown()


if __name__ == "__main__":
    main()
