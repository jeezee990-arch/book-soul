/**
 * 统一 API 封装：通过 Tauri invoke("api_request") → Rust → FastAPI。
 *
 * 错误处理：原样抛出 Rust 端的错误字符串（HTTP 4xx/5xx + body）。
 */

import { invoke } from "@tauri-apps/api/core";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * 调用后端任意 HTTP 端点。
 * @param method - HTTP 方法
 * @param path - 路径（必须以 / 开头，如 /novels、/novels/123）
 * @param body - 可选请求体
 */
export async function callApi<T = unknown>(
  method: HttpMethod,
  path: string,
  body?: unknown,
): Promise<T> {
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
