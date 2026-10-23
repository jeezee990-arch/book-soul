/**
 * 模型名自愈逻辑（alignModel）的单元测试。
 *
 * 背景：服务端会下线模型（mimo 的 mimo-v2.5-pro 就是在 2026-10 下线的）。
 * 配置里留着一个服务端不认的模型名 → 生成时直接 400。
 * alignModel 负责把"配置里的模型"对齐到"服务端现在还认的模型"。
 *
 * 这是纯逻辑，不依赖网络 / DOM。
 */

import { describe, expect, it } from "vitest";
import { alignModel, type ProviderModels } from "../settings";

function info(partial: Partial<ProviderModels>): ProviderModels {
  return {
    provider: "mimo",
    models: [],
    live_models: [],
    configured_models: [],
    default_model: "",
    reachable: true,
    message: "",
    ...partial,
  };
}

describe("alignModel", () => {
  it("没有模型清单时保持原值", () => {
    expect(alignModel("mimo-v2.6-pro", null)).toBe("mimo-v2.6-pro");
    expect(alignModel("mimo-v2.6-pro", info({}))).toBe("mimo-v2.6-pro");
  });

  it("当前模型仍在清单里 → 原样保留", () => {
    const m = info({
      models: ["mimo-v2.6-pro", "mimo-v2.5"],
      default_model: "mimo-v2.6-pro",
    });
    expect(alignModel("mimo-v2.5", m)).toBe("mimo-v2.5");
  });

  it("当前模型已被下线 → 回退到默认模型", () => {
    const m = info({
      models: ["mimo-v2.6-pro"],
      default_model: "mimo-v2.6-pro",
    });
    expect(alignModel("mimo-v2.5-pro", m)).toBe("mimo-v2.6-pro");
  });

  it("没有默认模型 → 取清单第一个", () => {
    const m = info({ models: ["a", "b"] });
    expect(alignModel("gone", m)).toBe("a");
  });

  it("当前模型为空 → 取默认模型", () => {
    const m = info({ models: ["a", "b"], default_model: "b" });
    expect(alignModel("", m)).toBe("b");
  });
});
