/**
 * 外观偏好（主题 / 纸面模式 / 正文字号）的单元测试。
 *
 * 为什么要有这些测试
 * --------------------
 * 这几项曾经各写各的：主题只在设置页的组件内存里，纸面模式 / 字号只存在
 * localStorage 且要打开设置页才读。结果是"重启后界面显示'跟随主题'、
 * 实际 DOM 上没有那个 class"这种割裂 —— 用户看得见、说不清。
 *
 * 现在统一由 zustand persist 管状态，由 AppShell 统一应用到 DOM。
 * 这里的测试锁住"重启能恢复"这条最关键的性质。
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  createAppearanceStore,
  DEFAULT_FONT_SIZE,
  FONT_SIZE_MAX,
  FONT_SIZE_MIN,
} from "../appearance-store";
import { createUIStore } from "../uiStore";

/** 内存版 storage（node 环境没有 localStorage）。 */
const mem = new Map<string, string>();
const memoryStorage = {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => {
    mem.set(k, v);
  },
  removeItem: (k: string) => {
    mem.delete(k);
  },
};

describe("appearance-store", () => {
  let store: ReturnType<typeof createAppearanceStore>;

  beforeEach(() => {
    mem.clear();
    store = createAppearanceStore(memoryStorage);
  });

  it("默认固定浅色纸面 + 默认字号", () => {
    const s = store.getState();
    expect(s.paperMode).toBe("paper");
    expect(s.fontSize).toBe(DEFAULT_FONT_SIZE);
  });

  it("可以切到跟随主题", () => {
    store.getState().setPaperMode("follow");
    expect(store.getState().paperMode).toBe("follow");
  });

  it("可以改字号", () => {
    store.getState().setFontSize(19);
    expect(store.getState().fontSize).toBe(19);
  });

  it("字号区间常量与设置页滑块一致", () => {
    expect(FONT_SIZE_MIN).toBe(13);
    expect(FONT_SIZE_MAX).toBe(22);
  });

  it("新实例能从持久化数据恢复（模拟重开应用）", async () => {
    store.getState().setPaperMode("follow");
    store.getState().setFontSize(20);
    await Promise.resolve();

    const restored = createAppearanceStore(memoryStorage);
    await restored.persist.rehydrate();
    expect(restored.getState().paperMode).toBe("follow");
    expect(restored.getState().fontSize).toBe(20);
  });
});

describe("ui-store 主题持久化", () => {
  let store: ReturnType<typeof createUIStore>;

  beforeEach(() => {
    mem.clear();
    store = createUIStore(memoryStorage);
  });

  it("默认深色", () => {
    expect(store.getState().theme).toBe("dark");
  });

  it("切主题会持久化", async () => {
    store.getState().setTheme("light");
    await Promise.resolve();
    expect(mem.get("book-soul-ui")).toBeTruthy();
  });

  it("新实例能恢复主题（模拟重开应用）", async () => {
    store.getState().setTheme("light");
    await Promise.resolve();

    const restored = createUIStore(memoryStorage);
    await restored.persist.rehydrate();
    expect(restored.getState().theme).toBe("light");
  });
});
