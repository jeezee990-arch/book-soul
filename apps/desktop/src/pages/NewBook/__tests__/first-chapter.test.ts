/**
 * `firstChapterOf` 的单元测试。
 *
 * 这是从大纲结构里取第一章的纯函数 —— 开新书完成后自动建章依赖它。
 */

import { describe, it, expect } from "vitest";
import { firstChapterOf } from "../first-chapter";

describe("firstChapterOf", () => {
  it("从 volumes[].chapters[] 取第一章", () => {
    const structure = {
      volumes: [
        { name: "第一卷", chapters: [{ title: "初入江湖", summary: "少年下山" }] },
        { name: "第二卷", chapters: [{ title: "风云突变" }] },
      ],
    };
    const first = firstChapterOf(structure);
    expect(first?.title).toBe("初入江湖");
    expect(first?.outline).toBe("少年下山");
  });

  it("概要拼上关键事件（每行一个 ·）", () => {
    const structure = {
      volumes: [
        {
          chapters: [
            {
              title: "初入江湖",
              summary: "少年下山",
              key_events: ["遇到师父", "首次比试"],
            },
          ],
        },
      ],
    };
    const first = firstChapterOf(structure);
    expect(first?.outline).toBe("少年下山\n· 遇到师父\n· 首次比试");
  });

  it("兼容单层 chapters[] 结构", () => {
    const structure = { chapters: [{ title: "序章", summary: "很久以前" }] };
    expect(firstChapterOf(structure)?.title).toBe("序章");
  });

  it("没有章节时返回 null", () => {
    expect(firstChapterOf({})).toBeNull();
    expect(firstChapterOf({ volumes: [] })).toBeNull();
    expect(firstChapterOf({ volumes: [{ name: "空卷" }] })).toBeNull();
  });

  it("没有概要和关键事件时 outline 为 null（不是空串）", () => {
    const structure = { volumes: [{ chapters: [{ title: "只有标题" }] }] };
    const first = firstChapterOf(structure);
    expect(first?.outline).toBeNull();
  });

  it("缺标题时用兜底标题，不返回 undefined", () => {
    const structure = { volumes: [{ chapters: [{ summary: "有概要" }] }] };
    expect(firstChapterOf(structure)?.title).toBe("第一章");
  });

  it("第一卷没有章节时继续找下一卷", () => {
    const structure = {
      volumes: [
        { name: "空卷", chapters: [] },
        { name: "有内容", chapters: [{ title: "第二章开头" }] },
      ],
    };
    expect(firstChapterOf(structure)?.title).toBe("第二章开头");
  });
});
