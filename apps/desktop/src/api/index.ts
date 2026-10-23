/**
 * 统一 API 封装：把「后端调用」收敛成一层，业务层只认 `callApi`。
 *
 * 两条通道：
 * - **Tauri 桌面版**：`invoke("api_request")` → Rust → FastAPI。
 *   后端地址由 Rust 侧分配（随机空闲端口），前端不硬编码。
 * - **纯浏览器**（`pnpm dev` 单独跑 vite，没起 Tauri）：`fetch` 直连后端。
 *   后端 CORS 已放行 `http://127.0.0.1:5173`（见 server/src/main.py）。
 *
 * 为什么必须有第二条通道：
 * 流式端点（`readNdjsonStream`）本来就是 fetch 直连后端的，普通请求却只能走
 * invoke —— 两套机制不一致。后果是 `pnpm dev` 单独跑时，页面能连上后端、
 * 却一个数据都拿不到（作品列表空、模型状态显示"未连接"）。
 * 这里把两条通道对齐：桌面版行为不变，纯浏览器多一条能用的路。
 */

import { invoke } from "@tauri-apps/api/core";
import { getBackendUrl } from "./backend";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/** 当前是否跑在 Tauri 运行时里（Tauri 2 会注入 `window.__TAURI_INTERNALS__`）。 */
function isTauriRuntime(): boolean {
  return (
    typeof window !== "undefined" &&
    "__TAURI_INTERNALS__" in (window as unknown as Record<string, unknown>)
  );
}

/** 把后端路径拼成绝对 URL（用于 fetch 直连）。 */
function absoluteUrl(base: string, path: string): string {
  const root = base.replace(/\/$/, "");
  return `${root}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * 纯浏览器通道：直接 fetch 后端。
 *
 * 错误语义与 Tauri 通道保持一致 —— 抛出 ApiError，消息里带方法、路径、状态码。
 */
async function callApiOverHttp<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<T> {
  const base = await getBackendUrl();
  const init: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  let resp: Response;
  try {
    resp = await fetch(absoluteUrl(base, path), init);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new ApiError(`${method} ${path} failed: ${msg}`);
  }

  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      detail = (await resp.text()) || detail;
    } catch {
      // 忽略读 body 失败
    }
    throw new ApiError(`${method} ${path} failed: ${detail}`);
  }

  if (resp.status === 204) {
    return undefined as T;
  }
  try {
    return (await resp.json()) as T;
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new ApiError(`${method} ${path} failed: invalid JSON (${msg})`);
  }
}

/**
 * 调用后端任意 HTTP 端点。
 *
 * @param method - HTTP 方法
 * @param path - 路径（必须以 / 开头，如 /novels、/novels/123）
 * @param body - 可选请求体
 */
export async function callApi<T = unknown>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<T> {
  if (!isTauriRuntime()) {
    return callApiOverHttp<T>(method, path, body);
  }

  try {
    return await invoke<T>("api_request", {
      method,
      path,
      body: body ?? null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new ApiError(`${method} ${path} failed: ${message}`);
  }
}
