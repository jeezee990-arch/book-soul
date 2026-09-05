/** 流式 ndjson 解析器（Phase 4.3 / 4.4 前端）。
 *
 * 后端用 StreamingResponse 返回 ``application/x-ndjson``，每行一个 JSON：
 * - ``{"text": "..."}`` 增量
 * - ``{"done": true, "provider": "..."}`` 收尾
 * - ``{"error": "..."}`` 失败
 *
 * 本模块把 ReadableStream 切成行，逐行解析成对象。
 */

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

export type StreamEvent = StreamDelta | StreamDone | StreamError;

export function isStreamDone(e: StreamEvent): e is StreamDone {
  return "done" in e && e.done === true;
}

export function isStreamError(e: StreamEvent): e is StreamError {
  return "error" in e && typeof (e as StreamError).error === "string";
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
  const url = absUrl(path, options.baseUrl);
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
