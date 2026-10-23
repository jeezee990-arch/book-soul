/**
 * `callApi` 浏览器通道的单元测试。
 *
 * 背景：桌面版走 Tauri `invoke("api_request")`，但纯浏览器（`pnpm dev` 单独跑）
 * 没有 Tauri 运行时，必须回落成 `fetch` 直连后端 —— 否则页面能连上后端
 * 却一个数据都拿不到（作品列表空、模型状态显示"未连接"）。
 *
 * vitest 默认跑在 node 环境，没有 `window.__TAURI_INTERNALS__`，
 * 所以这里天然走浏览器通道；桌面通道由 Tauri 运行时自己兜住。
 */

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../backend", () => ({
  getBackendUrl: vi.fn(async () => "http://127.0.0.1:8765"),
}));

import { ApiError, callApi } from "../index";

const fetchMock = vi.fn();

function stubFetch(response: Response) {
  fetchMock.mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
}

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe("callApi 浏览器通道", () => {
  it("GET 拼上后端地址并用 JSON 头", async () => {
    stubFetch(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const result = await callApi<{ ok: boolean }>("GET", "/novels");

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8765/novels");
    expect(init.method).toBe("GET");
    expect(init.body).toBeUndefined();
  });

  it("POST 序列化 body", async () => {
    stubFetch(new Response(JSON.stringify({ id: 7 }), { status: 200 }));

    await callApi("POST", "/novels", { name: "新书" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "新书" }));
  });

  it("路径没有前导斜杠时补上", async () => {
    stubFetch(new Response("{}", { status: 200 }));

    await callApi("GET", "settings");

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://127.0.0.1:8765/settings");
  });

  it("非 2xx → 抛 ApiError，消息含状态码与响应体", async () => {
    stubFetch(new Response('{"detail":"boom"}', { status: 400 }));

    await expect(callApi("GET", "/novels/999")).rejects.toBeInstanceOf(ApiError);
    await expect(callApi("GET", "/novels/999")).rejects.toThrow(/400/);
  });

  it("204 → 返回 undefined，不去解析 JSON", async () => {
    stubFetch(new Response(null, { status: 204 }));

    await expect(callApi("DELETE", "/novels/1")).resolves.toBeUndefined();
  });

  it("响应不是合法 JSON → 抛 ApiError", async () => {
    stubFetch(new Response("not json", { status: 200 }));

    await expect(callApi("GET", "/novels")).rejects.toBeInstanceOf(ApiError);
  });

  it("网络层抛错 → 包装成 ApiError", async () => {
    fetchMock.mockRejectedValue(new Error("ECONNREFUSED"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(callApi("GET", "/novels")).rejects.toBeInstanceOf(ApiError);
    await expect(callApi("GET", "/novels")).rejects.toThrow(/ECONNREFUSED/);
  });
});
