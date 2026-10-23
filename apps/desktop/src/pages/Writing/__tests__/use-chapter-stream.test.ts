/**
 * 章节落库内容选取（pickSavedContent）的单元测试。
 *
 * 这个函数守着一条容易犯错的规则：
 * - 流式**生成**是追加到章节末尾 → 流式累积量只有新增那部分
 * - 流式**重写**是替换选区 → 流式累积量只有新写的段落
 * 两种情况下，流式累积量都**不是**完整正文。
 * 如果直接把它存进版本，章节原有的正文会被抹掉。
 *
 * 所以：优先用编辑器里的完整全文，取不到才退回累积量。
 */

import { describe, expect, it } from "vitest";
import { pickSavedContent } from "../use-chapter-stream";

describe("pickSavedContent", () => {
  it("有完整正文时用完整正文（不是流式累积量）", () => {
    const full = "原有正文。\n\n新生成的一段。";
    expect(pickSavedContent(full, "只有新生成的一段")).toBe(full);
  });

  it("重写场景保留章节其余正文", () => {
    const full = "开头段落。\n\n改写后的段落。\n\n结尾段落。";
    const result = pickSavedContent(full, "改写后的段落。");
    expect(result).toContain("开头段落。");
    expect(result).toContain("结尾段落。");
    expect(result).not.toBe("改写后的段落。");
  });

  it("编辑器内容为空时退回流式累积量", () => {
    expect(pickSavedContent("", "累积量")).toBe("累积量");
    expect(pickSavedContent(undefined, "累积量")).toBe("累积量");
    expect(pickSavedContent(null, "累积量")).toBe("累积量");
  });

  it("编辑器内容只有空白时也退回累积量", () => {
    expect(pickSavedContent("   \n  ", "累积量")).toBe("累积量");
  });

  it("会去掉首尾空白", () => {
    expect(pickSavedContent("  正文  ", "x")).toBe("正文");
  });
});
