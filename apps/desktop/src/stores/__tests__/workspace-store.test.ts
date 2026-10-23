/**
 * 全局工作区状态（当前作品 / 当前章节）的单元测试。
 *
 * 为什么要有这些测试
 * --------------------
 * 这次 UI 重设计把"选作品"从三处重复下拉提升为**全局唯一状态**，
 * 并且要持久化（重开应用回到上次那本书）。
 * 一旦这里出错，用户会遇到"明明选了 A 书，切页后变成 B 书"这种
 * 极难自查的问题，所以逻辑必须被测试锁住。
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  createWorkspaceStore,
  WORKSPACE_STORAGE_KEY,
} from "../workspace-store";

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

describe("workspace-store", () => {
  let store: ReturnType<typeof createWorkspaceStore>;

  beforeEach(() => {
    mem.clear();
    store = createWorkspaceStore(memoryStorage);
  });

  it("初始状态为空", () => {
    const s = store.getState();
    expect(s.novelId).toBeNull();
    expect(s.chapterId).toBeNull();
    expect(s.chapterLabel).toBeNull();
  });

  it("切换作品会清掉章节（避免章节 id 串到另一本书）", () => {
    const s = store.getState();
    s.setNovelId(1);
    s.setChapterId(10, "第 10 章 · 试剑坪");
    expect(store.getState().chapterId).toBe(10);

    store.getState().setNovelId(2);
    const after = store.getState();
    expect(after.novelId).toBe(2);
    expect(after.chapterId).toBeNull();
    expect(after.chapterLabel).toBeNull();
  });

  it("重复设置同一作品保留当前章节", () => {
    const s = store.getState();
    s.setNovelId(1);
    s.setChapterId(10, "第 10 章");
    store.getState().setNovelId(1);
    expect(store.getState().chapterId).toBe(10);
    expect(store.getState().chapterLabel).toBe("第 10 章");
  });

  it("setTarget 一次性设置作品 + 章节 + 面包屑", () => {
    store.getState().setTarget(7, 42, "第 3 章 · 夜雨");
    const s = store.getState();
    expect(s.novelId).toBe(7);
    expect(s.chapterId).toBe(42);
    expect(s.chapterLabel).toBe("第 3 章 · 夜雨");
  });

  it("reset 清空全部", () => {
    store.getState().setTarget(1, 2, "x");
    store.getState().reset();
    const after = store.getState();
    expect(after.novelId).toBeNull();
    expect(after.chapterId).toBeNull();
    expect(after.chapterLabel).toBeNull();
  });

  it("状态会持久化（重开应用回到上次那本书）", () => {
    store.getState().setTarget(9, 99, "第 9 章");
    const raw = mem.get(WORKSPACE_STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw as string) as {
      state: { novelId: number; chapterId: number; chapterLabel: string };
    };
    expect(parsed.state.novelId).toBe(9);
    expect(parsed.state.chapterId).toBe(99);
    expect(parsed.state.chapterLabel).toBe("第 9 章");
  });

  it("新实例能从持久化数据恢复（模拟重开应用）", async () => {
    store.getState().setTarget(5, 55, "第 5 章 · 归来");
    // 让 persist 完成写入
    await Promise.resolve();

    const restored = createWorkspaceStore(memoryStorage);
    await restored.persist.rehydrate();
    const s = restored.getState();
    expect(s.novelId).toBe(5);
    expect(s.chapterId).toBe(55);
    expect(s.chapterLabel).toBe("第 5 章 · 归来");
  });
});
