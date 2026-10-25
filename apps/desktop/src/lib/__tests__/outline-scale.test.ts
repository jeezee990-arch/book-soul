/**
 * 大纲规模解析测试（2026-10-25 新增）。
 *
 * 覆盖用户真实场景：想法里写"共100章 / 每章3000字 / 完本30万字"，
 * 规模必须能被识别出来（否则想法会被 prompt 里的固定数字无视）。
 */

import { describe, expect, it } from "vitest";
import {
  DEFAULT_OUTLINE_SCALE,
  cnToInt,
  formatTotalWords,
  normalizeScale,
  parseScaleFromText,
  scaleTotalWords,
  scaleVolumeCount,
} from "../outline-scale";

describe("parseScaleFromText", () => {
  it("识别总章数", () => {
    const s = parseScaleFromText("共100章");
    expect(s?.totalChapters).toBe(100);
  });

  it("识别每卷章数（且不把它当成总章数）", () => {
    const s = parseScaleFromText("每卷10章");
    expect(s?.chaptersPerVolume).toBe(10);
    expect(s?.totalChapters).toBe(DEFAULT_OUTLINE_SCALE.totalChapters);
  });

  it("识别每章字数", () => {
    const s = parseScaleFromText("每章3000字");
    expect(s?.wordsPerChapter).toBe(3000);
  });

  it("识别 3k 写法", () => {
    const s = parseScaleFromText("每章 3k 字");
    expect(s?.wordsPerChapter).toBe(3000);
  });

  it("识别总字数并折算章数（30 万字 ÷ 3000 = 100 章）", () => {
    const s = parseScaleFromText("完本30万字");
    expect(s?.totalChapters).toBe(100);
  });

  it("识别 w 写法", () => {
    const s = parseScaleFromText("全书30w字");
    expect(s?.totalChapters).toBe(100);
  });

  it("总章数 + 每章字数 + 总字数一起识别", () => {
    const s = parseScaleFromText("总章数100章\n每章3000字\n完本30万字");
    expect(s?.totalChapters).toBe(100);
    expect(s?.wordsPerChapter).toBe(3000);
  });

  it("第 N 章里的数字不算总章数", () => {
    const s = parseScaleFromText("第10章开始");
    expect(s === null || s.totalChapters === DEFAULT_OUTLINE_SCALE.totalChapters).toBe(
      true,
    );
  });

  it("识别中文数字", () => {
    expect(cnToInt("一百二十")).toBe(120);
    expect(cnToInt("三十")).toBe(30);
    expect(cnToInt("abc")).toBeNull();
  });

  it("什么都没识别到时返回 null（不清零）", () => {
    expect(parseScaleFromText("主角是废柴，偶然获得传承")).toBeNull();
    expect(parseScaleFromText("")).toBeNull();
  });

  it("多行想法也能识别", () => {
    const s = parseScaleFromText("不要系统流\n主角是废柴\n共100章\n每卷10章");
    expect(s?.totalChapters).toBe(100);
    expect(s?.chaptersPerVolume).toBe(10);
  });
});

describe("normalizeScale", () => {
  it("缺省填默认值", () => {
    expect(normalizeScale()).toEqual(DEFAULT_OUTLINE_SCALE);
  });

  it("越界裁剪", () => {
    const s = normalizeScale({
      totalChapters: 99999,
      chaptersPerVolume: -5,
      wordsPerChapter: 1,
    });
    expect(s.totalChapters).toBe(500);
    expect(s.chaptersPerVolume).toBeGreaterThanOrEqual(1);
    expect(s.wordsPerChapter).toBeGreaterThanOrEqual(500);
  });

  it("每卷章数不超过总章数", () => {
    const s = normalizeScale({ totalChapters: 5, chaptersPerVolume: 20 });
    expect(s.chaptersPerVolume).toBe(5);
    expect(scaleVolumeCount(s)).toBe(1);
  });
});

describe("规模换算", () => {
  it("总卷数向上取整", () => {
    expect(scaleVolumeCount({ totalChapters: 25, chaptersPerVolume: 10, wordsPerChapter: 3000 })).toBe(3);
  });

  it("总字数与可读形式", () => {
    const s = { totalChapters: 100, chaptersPerVolume: 10, wordsPerChapter: 3000 };
    expect(scaleTotalWords(s)).toBe(300000);
    expect(formatTotalWords(300000)).toBe("30 万字");
  });
});
