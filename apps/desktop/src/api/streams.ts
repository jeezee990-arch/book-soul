/** 流式 ndjson 解析器（Phase 4.3 / 4.4 前端）。
 *
 * 后端用 StreamingResponse 返回 ``application/x-ndjson``，每行一个 JSON：
 * - ``{"text": "..."}`` 增量
 * - ``{"done": true, "provider": "..."}`` 收尾
 * - ``{"error": "..."}`` 失败
 *
 * 本模块把 ReadableStream 切成行，逐行解析成对象。
 */

import { getBackendUrl } from "./backend";

export interface StreamDelta {
  text: string;
}

export interface StreamDone {
  done: true;
  provider?: string;
  model?: string;
}

export interface StreamError {
  error: string;
}

/**
 * 推理模型的思考增量（``{"event": "thinking", "text": "..."}``）。
 *
 * ⚠️ 思考内容**不能丢**（AGENTS.md §4.7）：推理模型先吐好几秒 ``<think>``
 * 再写正文，丢掉思考 → 前端一个字都收不到 → 用户看到"生成卡住不动"。
 * 章节生成 / 重写 / 剧情 / 大纲都走这个事件。
 */
export interface StreamThinking {
  event: "thinking";
  text: string;
}

export type StreamEvent = StreamDelta | StreamDone | StreamError | StreamThinking;

export function isStreamDone(e: StreamEvent): e is StreamDone {
  return "done" in e && e.done === true;
}

export function isStreamError(e: StreamEvent): e is StreamError {
  return "error" in e && typeof (e as StreamError).error === "string";
}

/** 判断一个事件是不是"模型思考中"的增量。 */
export function isStreamThinking(e: StreamEvent): e is StreamThinking {
  return "event" in e && e.event === "thinking";
}

/** 流失败的来源。 */
export type StreamFailureSource = "transport" | "server";

/** 流失败信息（统一两类失败的出口）。 */
export interface StreamFailure {
  /** transport = HTTP 层失败（非 2xx / 无 body / 非法 JSON）；server = 后端流内错误帧。 */
  source: StreamFailureSource;
  message: string;
}

/**
 * 判断一个流事件是否代表失败；不是失败返回 null。
 *
 * ⚠️ 两类失败长得完全不一样，**漏掉任何一类都会让界面永远转圈**：
 *
 * - **transport**：`{ error: "422 Unprocessable Content" }` ——
 *   HTTP 非 2xx / 没有 body / NDJSON 解析失败，由 {@link readNdjsonStream} 产出。
 * - **server**：`{ event: "error", message: "..." }` ——
 *   后端在流中间发出的错误帧（见 `server/src/api/_stream_helpers.py` 的协议）。
 *
 * 只判断 `event === "error"` 的话，HTTP 422/500 会被静默吞掉：
 * generator 正常结束 → for-await 正常退出 → 没有任何分支命中 →
 * UI 停在"生成中…"不报错也不回退。这正是 2026-10-24 真机走查抓到的现象。
 */
export function detectStreamFailure(e: StreamEvent): StreamFailure | null {
  if (isStreamError(e)) {
    return { source: "transport", message: e.error };
  }
  const obj = e as unknown as Record<string, unknown>;
  if (obj.event === "error") {
    const msg = obj.message;
    return {
      source: "server",
      message: typeof msg === "string" && msg ? msg : "未知错误",
    };
  }
  return null;
}

/**
 * 大纲流事件的分类结果（2026-10-25 新增）。
 *
 * 后端大纲流协议（见 `server/src/services/outline_generator.py`）：
 * - `{"event": "start", "phase": "outline", "total_chapters": N, "volume_count": M, ...}`
 * - `{"event": "thinking", "text": "..."}` —— 模型思考中（带 `index` 的是某卷的思考）
 * - `{"event": "partial", "structure": {...}, "chapters_done": N}` —— **结构化**增量
 * - `{"event": "skeleton", "structure": {...}, "chapters_done": N}` —— 阶段一骨架完成
 * - `{"event": "volume_start" | "volume_done" | "volume_error", "index": i, ...}` —— 阶段二逐卷进度
 * - `{"event": "done", "novel_id": ..., "structure": {...}, "model": ..., "elapsed_sec": ...}`
 * - `{"event": "error", "message": "..."}`
 *
 * ⚠️ 2026-10-25 之前还有 `{"event": "delta", "text": "..."}` —— 那是 LLM 吐的
 * **原始 JSON**，前端用 `<pre>` 渲染就是一堆英文代码。现在后端不再发它，
 * 改成发已解析好的 `partial`。
 */
export type OutlineStreamEvent =
  | { kind: "thinking"; text: string; index: number | null }
  | { kind: "partial"; structure: Record<string, unknown>; chaptersDone: number }
  | { kind: "skeleton"; structure: Record<string, unknown>; chaptersDone: number }
  | { kind: "volume_start"; index: number; name: string }
  | { kind: "volume_done"; index: number; volume: Record<string, unknown> }
  | { kind: "volume_error"; index: number; message: string }
  | {
      kind: "done";
      novelId: number;
      novelName: string;
      structure: Record<string, unknown>;
      provider: string;
      model: string;
      elapsedSec: number | null;
      firstDeltaSec: number | null;
      skeletonSec: number | null;
      totalChapters: number | null;
      volumeCount: number | null;
    }
  | { kind: "error"; message: string }
  | { kind: "unknown" };

/**
 * 把一个 ndjson 事件解析成大纲流事件。
 *
 * 失败（两类：transport / server）统一走 {@link detectStreamFailure}，
 * 这里只处理"正常"的事件 —— 避免同一个错误被两个地方各判一遍、判出不同结果。
 */
export function parseOutlineStreamEvent(ev: StreamEvent): OutlineStreamEvent {
  const failure = detectStreamFailure(ev);
  if (failure) {
    return { kind: "error", message: failure.message };
  }
  const obj = ev as unknown as Record<string, unknown>;
  const event = obj.event as string | undefined;
  if (event === "thinking") {
    const idx = obj.index as number | undefined;
    return {
      kind: "thinking",
      text: (obj.text as string) ?? "",
      index: typeof idx === "number" ? idx : null,
    };
  }
  if (event === "partial" || event === "skeleton") {
    const structure = obj.structure as Record<string, unknown> | undefined;
    if (!structure) return { kind: "unknown" };
    const done = obj.chapters_done as number | undefined;
    return {
      kind: event === "skeleton" ? "skeleton" : "partial",
      structure,
      chaptersDone: typeof done === "number" ? done : 0,
    };
  }
  if (event === "volume_start") {
    return {
      kind: "volume_start",
      index: (obj.index as number) ?? 0,
      name: (obj.name as string) ?? "",
    };
  }
  if (event === "volume_done") {
    const volume = obj.volume as Record<string, unknown> | undefined;
    return {
      kind: "volume_done",
      index: (obj.index as number) ?? 0,
      volume: volume ?? {},
    };
  }
  if (event === "volume_error") {
    return {
      kind: "volume_error",
      index: (obj.index as number) ?? 0,
      message: (obj.message as string) ?? "未知错误",
    };
  }
  if (event === "done") {
    const elapsed = obj.elapsed_sec as number | undefined;
    const first = obj.first_delta_sec as number | null | undefined;
    const skeleton = obj.skeleton_sec as number | null | undefined;
    const totalChapters = obj.total_chapters as number | undefined;
    const volumeCount = obj.volume_count as number | undefined;
    return {
      kind: "done",
      novelId: (obj.novel_id as number) ?? 0,
      novelName: (obj.novel_name as string) ?? "",
      structure: (obj.structure as Record<string, unknown>) ?? {},
      provider: (obj.provider as string) ?? "",
      model: (obj.model as string) ?? "",
      elapsedSec: typeof elapsed === "number" ? elapsed : null,
      firstDeltaSec: typeof first === "number" ? first : null,
      skeletonSec: typeof skeleton === "number" ? skeleton : null,
      totalChapters: typeof totalChapters === "number" ? totalChapters : null,
      volumeCount: typeof volumeCount === "number" ? volumeCount : null,
    };
  }
  return { kind: "unknown" };
}

/** 把 baseUrl + path 拼成绝对 URL（用于 fetch + 流式 body）。 */
function absUrl(path: string, baseUrl?: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = baseUrl ?? "http://127.0.0.1:8765";
  return `${base.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}
export interface StreamOptions {
  method?: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
  baseUrl?: string;
}

/** 构造 ``readNdjsonStream`` 可直接用的 stream 请求对象（避免业务代码重复 ``method/body``）。 */
export interface StreamRequest {
  url: string;
  method: "GET" | "POST";
  body?: unknown;
  signal?: AbortSignal;
}

/** 把 ``StreamRequest`` + ``baseUrl`` 合并成 ``StreamOptions``。 */
export function streamRequestToOptions(
  req: StreamRequest,
  baseUrl?: string,
): StreamOptions {
  return {
    method: req.method,
    body: req.body,
    signal: req.signal,
    baseUrl,
  };
}

/** 从后端 ndjson 流读取事件，逐个 yield。
 *
 * 用法：
 * ```ts
 * for await (const ev of readNdjsonStream("/chapters/1/generate", { method: "POST", body: {...} })) {
 *   if (isStreamError(ev)) { toast.error(ev.error); return; }
 *   if (isStreamDone(ev)) { /* 完成 * / break; }
 *   // ev.text 是新片段
 * }
 * ```
 */
export async function* readNdjsonStream(
  path: string,
  options: StreamOptions = {},
): AsyncGenerator<StreamEvent> {
  // baseUrl 不传时向 Rust 要真实地址（桌面版是随机端口，不能硬编码）
  const base = options.baseUrl ?? (await getBackendUrl());
  const url = absUrl(path, base);
  const init: RequestInit = {
    method: options.method ?? "POST",
    headers: { "Content-Type": "application/json", Accept: "application/x-ndjson" },
  };
  if (options.body !== undefined) {
    init.body = JSON.stringify(options.body);
  }
  if (options.signal) {
    init.signal = options.signal;
  }

  const resp = await fetch(url, init);
  if (!resp.ok) {
    // 错误可能是 JSON（API 错误）也可能是 plain text
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      detail = j.detail ?? detail;
    } catch {
      try {
        detail = (await resp.text()) || detail;
      } catch {
        // 忽略
      }
    }
    yield { error: detail };
    return;
  }
  if (!resp.body) {
    yield { error: "No response body" };
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // 按 \n 切
      let nl = buffer.indexOf("\n");
      while (nl !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) {
          try {
            const obj = JSON.parse(line) as StreamEvent;
            yield obj;
          } catch {
            yield { error: `Invalid JSON: ${line.slice(0, 100)}` };
            return;
          }
        }
        nl = buffer.indexOf("\n");
      }
    }
    // 处理 buffer 残留
    if (buffer.trim()) {
      try {
        const obj = JSON.parse(buffer.trim()) as StreamEvent;
        yield obj;
      } catch {
        // 忽略残余不完整行
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }
}
