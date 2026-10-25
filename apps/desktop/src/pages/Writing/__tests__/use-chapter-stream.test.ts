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
import { classifyChapterStreamEvent, pickSavedContent } from "../use-chapter-stream";

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

/**
 * 章节流事件分类（2026-10-25 巡检修复）。
 *
 * 为什么要有这个纯函数：hook 本身要 DOM 环境，而本项目没装
 * @testing-library/react（不为了测试引入新依赖）。把"这个事件该怎么办"
 * 抽成纯函数后就能单测。
 *
 * 锁住三条规则：
 * 1. 两类失败都要认（transport / server）—— 漏一类界面就永远转圈；
 * 2. 思考事件单独一路，**不进正文**；
 * 3. 正文增量才进正文。
 */
describe("classifyChapterStreamEvent", () => {
  it("transport 失败（{ error }）→ fail", () => {
    expect(classifyChapterStreamEvent({ error: "422 Unprocessable Content" })).toEqual({
      kind: "fail",
      message: "422 Unprocessable Content",
    });
  });

  it("server 失败（{ event: 'error' }）→ fail", () => {
    expect(
      classifyChapterStreamEvent({ event: "error", message: "模型挂了" } as never),
    ).toEqual({ kind: "fail", message: "模型挂了" });
  });

  it("done 帧 → done", () => {
    expect(classifyChapterStreamEvent({ done: true })).toEqual({ kind: "done" });
  });

  it("思考事件 → thinking（不是 text，不会混进正文）", () => {
    expect(classifyChapterStreamEvent({ event: "thinking", text: "先想想" })).toEqual({
      kind: "thinking",
      text: "先想想",
    });
  });

  it("正文增量 → text", () => {
    expect(classifyChapterStreamEvent({ text: "正文" })).toEqual({
      kind: "text",
      text: "正文",
    });
  });

  it("不认识的帧 → ignore", () => {
    expect(classifyChapterStreamEvent({ foo: 1 } as never)).toEqual({ kind: "ignore" });
  });
});
