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
  detectStreamFailure,
  isStreamDone,
  isStreamError,
  isStreamThinking,
  parseOutlineStreamEvent,
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

  /**
   * 思考事件的识别（2026-10-25 新增）。
   *
   * ⚠️ 思考内容不能丢（AGENTS.md §4.7）：推理模型先吐好几秒 ``<think>``
   * 再写正文，丢掉思考 → 前端一个字都收不到 → 用户看到"生成卡住不动"。
   */
  it("isStreamThinking 只认 event=thinking", () => {
    expect(isStreamThinking({ event: "thinking", text: "先想想" })).toBe(true);
    expect(isStreamThinking({ event: "delta", text: "正文" } as never)).toBe(false);
    expect(isStreamThinking({ text: "正文" })).toBe(false);
    expect(isStreamThinking({ done: true })).toBe(false);
  });
});

describe("detectStreamFailure", () => {
  it("HTTP 层错误（{ error }）被识别为 transport 失败", () => {
    const f = detectStreamFailure({ error: "422 Unprocessable Content" });
    expect(f).toEqual({ source: "transport", message: "422 Unprocessable Content" });
  });

  it("后端流内错误帧（{ event: 'error' }）被识别为 server 失败", () => {
    const f = detectStreamFailure({ event: "error", message: "模型调用失败" } as never);
    expect(f).toEqual({ source: "server", message: "模型调用失败" });
  });

  it("流内错误帧缺 message 时给兜底文案，不返回空串", () => {
    const f = detectStreamFailure({ event: "error" } as never);
    expect(f).toEqual({ source: "server", message: "未知错误" });
  });

  it("正常事件不算失败", () => {
    expect(detectStreamFailure({ text: "x" })).toBeNull();
    expect(detectStreamFailure({ done: true })).toBeNull();
    expect(detectStreamFailure({ event: "delta", text: "x" } as never)).toBeNull();
  });
});

/**
 * 大纲流事件解析（2026-10-25 新增）。
 *
 * 为什么要有这个纯函数：后端大纲流协议改版了 —— 不再推原始 JSON 的
 * `delta` 事件，改推**已解析好**的 `partial`（卷 → 章 → 关键事件）。
 * 前端拿到就能直接渲染中文剧情，不需要解析半截 JSON。
 */
describe("parseOutlineStreamEvent", () => {
  it("thinking 事件 → kind=thinking", () => {
    const r = parseOutlineStreamEvent({ event: "thinking", text: "先想想" } as never);
    // ⚠️ 2026-10-25 两阶段大纲：thinking 可能带 index（某卷的思考）
    expect(r).toEqual({ kind: "thinking", text: "先想想", index: null });
  });

  it("thinking 事件带 index（某卷的思考）", () => {
    const r = parseOutlineStreamEvent({
      event: "thinking",
      index: 2,
      text: "在编第二卷",
    } as never);
    expect(r).toEqual({ kind: "thinking", text: "在编第二卷", index: 2 });
  });

  it("skeleton 事件 → 结构 + 章节数（阶段一完成）", () => {
    const structure = { volumes: [{ name: "第一卷" }] };
    const r = parseOutlineStreamEvent({
      event: "skeleton",
      structure,
      chapters_done: 12,
    } as never);
    expect(r).toEqual({ kind: "skeleton", structure, chaptersDone: 12 });
  });

  it("volume_done 事件 → 卷下标 + 细化后的卷", () => {
    const volume = { name: "第一卷", chapters: [{ summary: "概要" }] };
    const r = parseOutlineStreamEvent({
      event: "volume_done",
      index: 0,
      volume,
    } as never);
    expect(r).toEqual({ kind: "volume_done", index: 0, volume });
  });

  it("volume_error 事件 → 卷下标 + 错误信息", () => {
    const r = parseOutlineStreamEvent({
      event: "volume_error",
      index: 1,
      message: "超时",
    } as never);
    expect(r).toEqual({ kind: "volume_error", index: 1, message: "超时" });
  });

  it("partial 事件 → 结构 + 已完成章节数", () => {
    const structure = { volumes: [{ name: "第一卷" }] };
    const r = parseOutlineStreamEvent({
      event: "partial",
      structure,
      chapters_done: 3,
    } as never);
    expect(r).toEqual({ kind: "partial", structure, chaptersDone: 3 });
  });

  it("partial 事件缺 chapters_done 时按 0 处理", () => {
    const structure = { volumes: [] };
    const r = parseOutlineStreamEvent({ event: "partial", structure } as never);
    expect(r.kind).toBe("partial");
    if (r.kind === "partial") expect(r.chaptersDone).toBe(0);
  });

  it("done 事件 → 作品信息 + 模型 + 耗时 + 首字延迟", () => {
    const structure = { volumes: [] };
    const r = parseOutlineStreamEvent({
      event: "done",
      novel_id: 7,
      novel_name: "灵根重塑",
      structure,
      provider: "minimax",
      model: "MiniMax-M3.1-Flash",
      elapsed_sec: 12.34,
      first_delta_sec: 1.5,
    } as never);
    expect(r).toEqual({
      kind: "done",
      novelId: 7,
      novelName: "灵根重塑",
      structure,
      provider: "minimax",
      model: "MiniMax-M3.1-Flash",
      elapsedSec: 12.34,
      firstDeltaSec: 1.5,
      skeletonSec: null,
      totalChapters: null,
      volumeCount: null,
    });
  });

  it("done 事件带两阶段耗时与规模", () => {
    const r = parseOutlineStreamEvent({
      event: "done",
      novel_id: 1,
      elapsed_sec: 40,
      first_delta_sec: 2,
      skeleton_sec: 18,
      total_chapters: 100,
      volume_count: 10,
    } as never);
    expect(r.kind).toBe("done");
    if (r.kind === "done") {
      expect(r.skeletonSec).toBe(18);
      expect(r.totalChapters).toBe(100);
      expect(r.volumeCount).toBe(10);
    }
  });

  it("done 事件缺耗时字段 → null（不编造数字）", () => {
    const r = parseOutlineStreamEvent({ event: "done", novel_id: 1 } as never);
    expect(r.kind).toBe("done");
    if (r.kind === "done") {
      expect(r.elapsedSec).toBeNull();
      expect(r.firstDeltaSec).toBeNull();
    }
  });

  it("transport 失败（{ error }）→ kind=error", () => {
    const r = parseOutlineStreamEvent({ error: "422 Unprocessable Content" });
    expect(r).toEqual({ kind: "error", message: "422 Unprocessable Content" });
  });

  it("server 失败（{ event: 'error' }）→ kind=error", () => {
    const r = parseOutlineStreamEvent({ event: "error", message: "结构无效" } as never);
    expect(r).toEqual({ kind: "error", message: "结构无效" });
  });

  it("不认识的事件 → kind=unknown（不当作错误）", () => {
    const r = parseOutlineStreamEvent({ event: "phase", phase: "cards" } as never);
    expect(r).toEqual({ kind: "unknown" });
  });
});

describe("streamRequestToOptions", () => {  it("原样透传 method / body / signal / baseUrl", () => {
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
