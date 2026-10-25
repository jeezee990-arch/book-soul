/**
 * 开新书进度 store 的单元测试。
 *
 * 为什么要有这些测试
 * --------------------
 * 用户反馈过："切换到其他界面返回后，还是会保留原本的进度，
 * 不要一离开界面开新书进度就清空"。
 *
 * 这里的逻辑一旦出错，用户会遇到"填了半小时想法，切个页面全没了"
 * —— 比功能缺失更让人恼火，所以必须锁住。
 */

import { beforeEach, describe, expect, it } from "vitest";
import { createNewBookStore, NEWBOOK_STORAGE_KEY } from "../newbook-store";

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

describe("newbook-store", () => {
  let store: ReturnType<typeof createNewBookStore>;

  beforeEach(() => {
    mem.clear();
    store = createNewBookStore(memoryStorage);
  });

  it("初始状态是第一步、无任何内容", () => {
    const s = store.getState();
    expect(s.step).toBe("seed");
    expect(s.genre).toBeNull();
    expect(s.keywords).toEqual([]);
    expect(s.ideas).toEqual([]);
    expect(s.plotVersions).toEqual([]);
    expect(s.outlineMode).toBe("complete");
  });

  it("想法词条：逐条添加、可按下标删除", () => {
    const s = store.getState();
    s.addIdea("完本30w字，每章3k字");
    store.getState().addIdea("主角别太开挂");
    expect(store.getState().ideas).toEqual([
      "完本30w字，每章3k字",
      "主角别太开挂",
    ]);

    store.getState().removeIdea(0);
    expect(store.getState().ideas).toEqual(["主角别太开挂"]);
  });

  it("关键词：切换添加 / 再点移除", () => {
    const s = store.getState();
    s.toggleKeyword("密室");
    expect(store.getState().keywords).toEqual(["密室"]);
    store.getState().toggleKeyword("失忆");
    expect(store.getState().keywords).toEqual(["密室", "失忆"]);
    store.getState().toggleKeyword("密室");
    expect(store.getState().keywords).toEqual(["失忆"]);
  });

  it("剧情版本支持函数式更新（流式追加不能基于旧闭包）", () => {
    const s = store.getState();
    s.setPlotVersions([{ index: 1, summary: "A" }]);
    store.getState().setPlotVersions((prev) => [
      ...prev,
      { index: 2, summary: "B" },
    ]);
    expect(store.getState().plotVersions).toHaveLength(2);
    expect(store.getState().plotVersions[1].index).toBe(2);
  });

  it("人物卡进度支持函数式更新", () => {
    const s = store.getState();
    s.setCharProgress({ extracted: [{ name: "沈砚", role: "主角" }], cards: [] });
    store.getState().setCharProgress((prev) => ({
      ...prev,
      cards: [...prev.cards, { name: "裴无咎", role: "反派", text: "" }],
    }));
    expect(store.getState().charProgress.cards).toHaveLength(1);
  });

  it("进度会持久化（切页面回来还在）", () => {
    const s = store.getState();
    s.setStep("plot");
    s.addIdea("保留这条想法");
    s.toggleKeyword("密室");

    const raw = mem.get(NEWBOOK_STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw as string) as {
      state: { step: string; ideas: string[]; keywords: string[] };
    };
    expect(parsed.state.step).toBe("plot");
    expect(parsed.state.ideas).toEqual(["保留这条想法"]);
    expect(parsed.state.keywords).toEqual(["密室"]);
  });

  it("新实例能从持久化数据恢复（模拟重开应用）", async () => {
    store.getState().setStep("outline");
    store.getState().addIdea("留个悬念");
    store.getState().setChosenPlotIdx(2);
    await Promise.resolve();

    const restored = createNewBookStore(memoryStorage);
    await restored.persist.rehydrate();
    const s = restored.getState();
    expect(s.step).toBe("outline");
    expect(s.ideas).toEqual(["留个悬念"]);
    expect(s.chosenPlotIdx).toBe(2);
  });

  it("流式中间态不写进持久化（避免每次进页面 rehydrate 一大坨文本）", () => {
    store.getState().setPlotBusy(true);
    store.getState().setPlotStreaming({ 1: "正在写的内容" });
    store.getState().setOutlinePartial({ volumes: [] });

    const raw = mem.get(NEWBOOK_STORAGE_KEY);
    const parsed = JSON.parse(raw as string) as {
      state: Record<string, unknown>;
    };
    expect(parsed.state.plotBusy).toBeUndefined();
    expect(parsed.state.plotStreaming).toBeUndefined();
    expect(parsed.state.outlinePartial).toBeUndefined();
  });

  it("resetAll 清空全部进度", () => {
    const s = store.getState();
    s.setStep("plot");
    s.addIdea("x");
    s.setChosenPlotIdx(1);
    store.getState().resetAll();
    const after = store.getState();
    expect(after.step).toBe("seed");
    expect(after.ideas).toEqual([]);
    expect(after.chosenPlotIdx).toBeNull();
  });
});
