/**
 * 后端地址解析 + 就绪握手。
 *
 * 桌面版（Tauri）下 Rust 侧会：
 * 1. 分配一个**随机空闲端口**（避免多开冲突 / 旧进程残留）
 * 2. 自动拉起 Python 后端
 * 3. 通过 command 把真实地址下发
 *
 * 所以前端**不能硬编码 127.0.0.1:8765**，必须先问 Rust。
 * 开发模式（Vite 单独跑、无 Tauri）才回落到默认端口。
 */

import { invoke } from "@tauri-apps/api/core";

/** dev 模式（不经过 Tauri）时的默认后端地址 */
const DEV_FALLBACK = "http://127.0.0.1:8765";

let cachedUrl: string | null = null;
let cachedDataDir: string | null = null;

/** 取后端根地址（带缓存）。 */
export async function getBackendUrl(): Promise<string> {
  if (cachedUrl) return cachedUrl;
  try {
    cachedUrl = await invoke<string>("get_backend_url");
  } catch {
    // 没跑在 Tauri 里（纯 vite dev / 单元测试）→ 回落默认端口
    cachedUrl = DEV_FALLBACK;
  }
  return cachedUrl;
}

/** 取数据目录（便携模式下是 exe 同级 data/）。取不到返回空串。 */
export async function getDataDir(): Promise<string> {
  if (cachedDataDir !== null) return cachedDataDir;
  try {
    cachedDataDir = await invoke<string>("get_data_dir");
  } catch {
    cachedDataDir = "";
  }
  return cachedDataDir;
}

/**
 * 等后端就绪。
 *
 * @param timeoutMs 最长等待（默认 30s）
 * @returns true = 后端已就绪；false = 超时
 */
export async function waitBackendReady(timeoutMs = 30_000): Promise<boolean> {
  try {
    return await invoke<boolean>("backend_ready", { timeoutMs });
  } catch {
    // 不在 Tauri 里 → 直接打 /ping 探活
    try {
      const resp = await fetch(`${DEV_FALLBACK}/ping`, {
        signal: AbortSignal.timeout(2000),
      });
      return resp.ok;
    } catch {
      return false;
    }
  }
}

/** 测试用：清缓存。 */
export function resetBackendCache(): void {
  cachedUrl = null;
  cachedDataDir = null;
}
