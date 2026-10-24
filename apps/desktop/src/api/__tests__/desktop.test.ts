/**
 * 桌面壳 API 与 LLM 端点封装的单元测试。
 *
 * 覆盖两处本轮改动：
 * 1. ``llmApi.listModels(provider, refresh)`` —— refresh=true 时要带上
 *    ``&refresh=true``，否则「刷新列表」按钮拿到的还是缓存里的旧清单。
 * 2. ``desktopApi.openDataDir`` —— 设置页「在文件夹中显示」要真的调
 *    Rust 侧的 command（之前只是个 toast 提示，什么都没发生）。
 *
 * 注意：vitest 默认跑在 node 环境，没有 ``window.__TAURI_INTERNALS__``，
 * ``callApi`` 会回落成浏览器 fetch 通道。这里显式把 Tauri 运行时桩出来，
 * 让断言落在 invoke 通道上（浏览器通道由 ``transport.test.ts`` 单独覆盖）。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
}));

vi.mock("../backend", () => ({
  getBackendUrl: vi.fn(async () => "http://127.0.0.1:8765"),
}));

import { llmApi } from "../settings";
import { desktopApi } from "../desktop";

/**
 * 记下 invoke 最近一次收到的 path。
 *
 * invoke("api_request", { method, path, body }) 的第 2 个参数是参数对象，
 * path 在它的 .path 上。
 */
function lastPath(): string {
  const calls = invokeMock.mock.calls;
  const args = calls[calls.length - 1]?.[1] as { path?: string } | undefined;
  return String(args?.path ?? "");
}

beforeEach(() => {
  // 桩出 Tauri 运行时，让 callApi 走 invoke 通道而不是 fetch
  vi.stubGlobal("window", { __TAURI_INTERNALS__: {} });
  invokeMock.mockReset();
  invokeMock.mockResolvedValue({
    models: ["m1"],
    live_models: ["m1"],
    configured_models: [],
    default_model: "m1",
    reachable: true,
    message: "",
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("llmApi.listModels", () => {
  it("默认走缓存：不带 refresh 参数", async () => {
    await llmApi.listModels("mimo");
    expect(lastPath()).toBe("/llm/models?provider=mimo");
  });

  it("refresh=true 时强制绕过服务端缓存", async () => {
    await llmApi.listModels("mimo", true);
    expect(lastPath()).toBe("/llm/models?provider=mimo&refresh=true");
  });
});

describe("desktopApi.openDataDir", () => {
  it("调 Rust 的 open_data_dir command", async () => {
    await desktopApi.openDataDir();
    const call = invokeMock.mock.calls[0];
    expect(call[0]).toBe("open_data_dir");
  });

  it("失败时把错误透出去（调用方要能降级提示）", async () => {
    invokeMock.mockRejectedValueOnce(new Error("没有这个 command"));
    await expect(desktopApi.openDataDir()).rejects.toThrow("没有这个 command");
  });
});

describe("llmApi.health", () => {
  it("指定 provider 时只探活这一个（顶栏灯用）", async () => {
    await llmApi.health("mimo");
    expect(lastPath()).toBe("/llm/health?provider=mimo");
  });

  it("不指定 provider 时探活全部", async () => {
    await llmApi.health();
    expect(lastPath()).toBe("/llm/health");
  });
});
