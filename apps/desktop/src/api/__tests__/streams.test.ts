/**
 * 流式 ndjson 解析器的单元测试。
 *
 * 为什么必须有这些测试
 * --------------------
 * 用户报过"流式输出跟阻塞一样"。后端那边用契约测试锁住了
 * （`server/tests/test_llm_streaming_contract.py`），前端这边也必须有对应的锁：
 *
 * - **分块边界**：网络分片和"一行 JSON"没有对应关系，一个 JSON 对象
 *   完全可能被拆到两个 chunk 里。解析器必须自己拼起来。
 * - **无换行收尾**：最后一行没有 `\n` 结尾是合法的，不能丢。
 * - **非法 JSON**：不能整个崩掉，要 yield 一个 error 事件让 UI 能提示。
 *
 * 这些是纯逻辑测试，不依赖 DOM / React，跑得快、改起来不怕。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// backend 模块会去调 Tauri 的 invoke，测试里直接 mock 掉
vi.mock("../backend", () => ({
  getBackendUrl: vi.fn(async () => "http://127.0.0.1:8765"),
}));

import {
  isStreamDone,
  isStreamError,
  readNdjsonStream,
  streamRequestToOptions,
  type StreamEvent,
} from "../streams";

/** 造一个假的 Response（只需要 body / ok / status 这些字段）。 */
function fakeResponse(
  chunks: string[],
  init: { ok?: boolean; status?: number; statusText?: string } = {},
) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) {
        controller.enqueue(encoder.encode(c));
      }
      controller.close();
    },
  });
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: init.statusText ?? "OK",
    body,
    json: async () => ({}),
    text: async () => chunks.join(""),
  };
}

/** 把 async generator 收集成数组。 */
async function collect(gen: AsyncGenerator<StreamEvent>): Promise<StreamEvent[]> {
  const out: StreamEvent[] = [];
  for await (const ev of gen) {
    out.push(ev);
  }
  return out;
}

describe("类型守卫", () => {
  it("isStreamDone 只认 done:true", () => {
    expect(isStreamDone({ done: true })).toBe(true);
    expect(isStreamDone({ done: false } as never)).toBe(false);
    expect(isStreamDone({ text: "x" })).toBe(false);
  });

  it("isStreamError 只认字符串 error", () => {
    expect(isStreamError({ error: "boom" })).toBe(true);
    expect(isStreamError({ error: 123 } as never)).toBe(false);
    expect(isStreamError({ text: "x" })).toBe(false);
  });
});

describe("streamRequestToOptions", () => {
  it("原样透传 method / body / signal / baseUrl", () => {
    const ctrl = new AbortController();
    const opts = streamRequestToOptions(
      { url: "/x", method: "POST", body: { a: 1 }, signal: ctrl.signal },
      "http://h:1",
    );
    expect(opts.method).toBe("POST");
    expect(opts.body).toEqual({ a: 1 });
    expect(opts.signal).toBe(ctrl.signal);
    expect(opts.baseUrl).toBe("http://h:1");
  });
});

describe("readNdjsonStream", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("逐行 yield 正常事件", async () => {
    fetchMock.mockResolvedValue(
      fakeResponse([
        '{"text":"你"}\n',
        '{"text":"好"}\n',
        '{"done":true,"provider":"openai"}\n',
      ]),
    );
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([
      { text: "你" },
      { text: "好" },
      { done: true, provider: "openai" },
    ]);
  });

  it("JSON 被拆到两个 chunk 里也能正确拼回来", async () => {
    // 这是最容易出错的场景：网络分片和"一行 JSON"没有对应关系
    fetchMock.mockResolvedValue(
      fakeResponse(['{"text":"完整的一句', '话"}\n{"done":true}\n']),
    );
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([{ text: "完整的一句话" }, { done: true }]);
  });

  it("单字符逐个到达（最极端的流式）也能正确解析", async () => {
    const line = '{"text":"abc"}\n{"done":true}\n';
    fetchMock.mockResolvedValue(fakeResponse(line.split("")));
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([{ text: "abc" }, { done: true }]);
  });

  it("最后一行没有换行符也不丢", async () => {
    fetchMock.mockResolvedValue(fakeResponse(['{"text":"尾巴"}\n{"done":true}']));
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([{ text: "尾巴" }, { done: true }]);
  });

  it("空行被跳过", async () => {
    fetchMock.mockResolvedValue(fakeResponse(['\n\n{"text":"x"}\n\n']));
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([{ text: "x" }]);
  });

  it("非法 JSON → yield error 事件而不是抛异常", async () => {
    fetchMock.mockResolvedValue(fakeResponse(["{这不是 json}\n"]));
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toHaveLength(1);
    expect(isStreamError(events[0])).toBe(true);
    expect((events[0] as { error: string }).error).toContain("Invalid JSON");
  });

  it("HTTP 非 2xx → yield error 事件", async () => {
    fetchMock.mockResolvedValue(
      fakeResponse([""], { ok: false, status: 500, statusText: "Server Error" }),
    );
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toHaveLength(1);
    expect(isStreamError(events[0])).toBe(true);
  });

  it("没有 body → yield error 事件", async () => {
    const resp = { ok: true, status: 200, statusText: "OK", body: null };
    fetchMock.mockResolvedValue(resp);
    const events = await collect(readNdjsonStream("/x", { baseUrl: "http://h:1" }));
    expect(events).toEqual([{ error: "No response body" }]);
  });

  it("相对路径会拼上 baseUrl", async () => {
    fetchMock.mockResolvedValue(fakeResponse(["{}\n"]));
    await collect(readNdjsonStream("/api/x", { baseUrl: "http://127.0.0.1:9999/" }));
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:9999/api/x");
  });

  it("绝对路径原样使用", async () => {
    fetchMock.mockResolvedValue(fakeResponse(["{}\n"]));
    await collect(readNdjsonStream("http://other:1/x", { baseUrl: "http://127.0.0.1:9999" }));
    expect(fetchMock.mock.calls[0][0]).toBe("http://other:1/x");
  });

  it("POST 会带上 JSON body 和 ndjson Accept 头", async () => {
    fetchMock.mockResolvedValue(fakeResponse(["{}\n"]));
    await collect(
      readNdjsonStream("/x", {
        baseUrl: "http://h:1",
        method: "POST",
        body: { k: "v" },
      }),
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"k":"v"}');
    expect((init.headers as Record<string, string>).Accept).toBe("application/x-ndjson");
  });
});
