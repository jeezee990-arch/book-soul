/**
 * 正文纯文本处理测试（2026-10-30）。
 *
 * ⚠️ 口径必须与后端 `server/src/core/prose_format.py` 完全一致，
 *    否则界面字数和导出文档对不上。
 */

import { describe, expect, it } from "vitest";
import {
  countProseWords,
  escapeHtml,
  plainTextToParagraphHtml,
  splitParagraphs,
} from "../prose-text";

describe("splitParagraphs", () => {
  it("按空行分段", () => {
    expect(splitParagraphs("第一段\n\n第二段")).toEqual(["第一段", "第二段"]);
  });

  it("单个换行也当分段", () => {
    expect(splitParagraphs("第一段\n第二段")).toEqual(["第一段", "第二段"]);
  });

  it("丢弃空段", () => {
    expect(splitParagraphs("\n\n甲\n\n\n\n乙\n\n")).toEqual(["甲", "乙"]);
  });

  it("去掉每段首尾空白", () => {
    expect(splitParagraphs("  甲  \n\n  乙  ")).toEqual(["甲", "乙"]);
  });

  it("兼容 CRLF", () => {
    expect(splitParagraphs("甲\r\n\r\n乙")).toEqual(["甲", "乙"]);
  });

  it("空文本返回空数组", () => {
    expect(splitParagraphs("")).toEqual([]);
  });
});

describe("countProseWords", () => {
  it("汉字与中文标点都算", () => {
    expect(countProseWords("你好世界")).toBe(4);
    expect(countProseWords("你好，世界！")).toBe(6);
  });

  it("空格与换行都不算", () => {
    expect(countProseWords("你 好\n\n世界")).toBe(4);
    expect(countProseWords("甲。\n\n乙。")).toBe(4);
  });

  it("全角空格也不算", () => {
    expect(countProseWords("甲　乙")).toBe(2);
  });

  it("英文按字符算（非空白字符数口径）", () => {
    expect(countProseWords("hello world")).toBe(10);
  });

  it("空文本为 0", () => {
    expect(countProseWords("")).toBe(0);
  });

  it("与用户实测数据一致：坏数据的虚高来自换行符", () => {
    // 用户库《骨仙传》第 1 章：len=5338，其中 2024 个是换行 → 真实 3314
    const broken = "山\n\n门前的\n\n铜\n\n钟连\n\n响三\n\n声";
    expect(broken.length).toBe(20);
    expect(countProseWords(broken)).toBe(10);
  });
});

describe("escapeHtml", () => {
  it("转义尖括号与和号", () => {
    expect(escapeHtml("<他在笑> & 走了")).toBe(
      "&lt;他在笑&gt; &amp; 走了",
    );
  });
});

describe("plainTextToParagraphHtml", () => {
  it("每段一个 <p>", () => {
    expect(plainTextToParagraphHtml("甲\n\n乙")).toBe("<p>甲</p><p>乙</p>");
  });

  it("段内尖括号被转义", () => {
    expect(plainTextToParagraphHtml("<他在笑>")).toBe(
      "<p>&lt;他在笑&gt;</p>",
    );
  });

  it("空文本返回空串", () => {
    expect(plainTextToParagraphHtml("")).toBe("");
  });
});
