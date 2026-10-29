/**
 * 两阶段大纲的前端合并测试（2026-10-25 新增）。
 *
 * 后端按卷下标下发 `volume_done`，前端要按下标替换对应卷的章节细节 ——
 * 合并逻辑错了就会出现"第 2 卷的概要跑到第 1 卷"。
 */

import { describe, expect, it } from "vitest";
import { mergeVolumeIntoStructure, fillPendingChapters } from "../outline-merge";

const skeleton = {
  volumes: [
    { name: "第一卷", chapters: [{ title: "A" }, { title: "B" }] },
    { name: "第二卷", chapters: [{ title: "C" }] },
  ],
};

describe("mergeVolumeIntoStructure", () => {
  it("把细节合并到对应下标的卷", () => {
    const merged = mergeVolumeIntoStructure(skeleton, 1, {
      name: "第二卷",
      chapters: [{ summary: "概要C", key_events: ["事件1", "事件2"] }],
    });
    const volumes = merged.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].summary).toBeUndefined();
    expect(volumes[1].chapters[0].summary).toBe("概要C");
    expect(volumes[1].chapters[0].key_events).toEqual(["事件1", "事件2"]);
  });

  it("保留骨架里的标题（细节阶段不改标题）", () => {
    const merged = mergeVolumeIntoStructure(skeleton, 0, {
      chapters: [{ title: "被改的标题", summary: "概要A" }],
    });
    const volumes = merged.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].title).toBe("A");
  });

  it("缺失的细节不覆盖骨架原值", () => {
    const merged = mergeVolumeIntoStructure(skeleton, 0, {});
    const volumes = merged.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].summary).toBeUndefined();
    expect(volumes[0].chapters[0].key_events).toEqual([]);
  });

  it("不修改入参", () => {
    mergeVolumeIntoStructure(skeleton, 0, { chapters: [{ summary: "x" }] });
    const volumes = skeleton.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].summary).toBeUndefined();
  });

  it("下标越界时原样返回", () => {
    const merged = mergeVolumeIntoStructure(skeleton, 9, { chapters: [] });
    expect(merged).toBe(skeleton);
  });
});

/**
 * 需求7：失败的卷不能只剩标题 —— 流式阶段就要补占位概要，
 * 与后端 merge_volume_details 保持一致。
 */
describe("fillPendingChapters", () => {
  it("给没有概要的章节补占位（标注待细化）", () => {
    const merged = fillPendingChapters(skeleton, 1);
    const volumes = merged.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[1].chapters[0].summary).toContain("待细化");
    expect(volumes[1].chapters[0].title).toBe("C");
    expect(volumes[1].chapters[0].key_events).toEqual([]);
  });

  it("已经有概要的章节不被覆盖", () => {
    const withSummary = {
      volumes: [{ name: "第一卷", chapters: [{ title: "A", summary: "已有概要" }] }],
    };
    const merged = fillPendingChapters(withSummary, 0);
    const volumes = merged.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].summary).toBe("已有概要");
  });

  it("不修改入参", () => {
    fillPendingChapters(skeleton, 0);
    const volumes = skeleton.volumes as { chapters: Record<string, unknown>[] }[];
    expect(volumes[0].chapters[0].summary).toBeUndefined();
  });

  it("下标越界时原样返回", () => {
    expect(fillPendingChapters(skeleton, 9)).toBe(skeleton);
  });
});
