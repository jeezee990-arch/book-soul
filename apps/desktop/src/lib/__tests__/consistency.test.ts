/**
 * 一致性检查的单元测试（2026-10-25 新增）。
 *
 * 覆盖需求里的两条检测：
 * - 剧情是否符合**种子词条**
 * - 大纲是否符合**剧情走向**
 */

import { describe, expect, it } from "vitest";
import {
  checkKeywordCoverage,
  checkOutlineCoverage,
  coveragePercent,
  extractKeyTerms,
  structureToText,
} from "../consistency";

describe("checkKeywordCoverage", () => {
  it("精确子串命中算覆盖", () => {
    const r = checkKeywordCoverage("主角是废柴，靠复仇逆袭", ["废柴", "复仇"]);
    expect(r.matched).toEqual(["废柴", "复仇"]);
    expect(r.missing).toEqual([]);
    expect(ratio(r)).toBe(1);
  });

  it("没提到的词算缺失", () => {
    const r = checkKeywordCoverage("主角是废柴", ["废柴", "系统流", "修仙"]);
    expect(r.matched).toEqual(["废柴"]);
    expect(r.missing).toEqual(["系统流", "修仙"]);
    expect(coveragePercent(r)).toBe(33);
  });

  it("空词条列表返回 100%（不报错、不误报）", () => {
    const r = checkKeywordCoverage("随便什么", []);
    expect(r.total).toBe(0);
    expect(coveragePercent(r)).toBe(100);
  });

  it("忽略空白词条", () => {
    const r = checkKeywordCoverage("文本", ["  ", "文本"]);
    expect(r.total).toBe(1);
  });
});

describe("extractKeyTerms", () => {
  it("抽取重复出现的 2 字词", () => {
    const terms = extractKeyTerms("主角在修仙宗门里修仙宗门里苦修，最后复仇修仙", 5);
    expect(terms.length).toBeGreaterThan(0);
    expect(terms).toContain("修仙");
  });

  it("只出现一次的词不取（噪声）", () => {
    const terms = extractKeyTerms("孤零零", 5);
    expect(terms).toEqual([]);
  });
});

describe("structureToText", () => {
  it("把卷章结构摊平成文本", () => {
    const text = structureToText({
      overall_theme: "凡人修仙",
      volumes: [
        {
          name: "第一卷 觉醒",
          summary: "主角觉醒血脉",
          chapters: [{ title: "第一章 变故", summary: "家族被灭", key_events: ["夜袭"] }],
        },
      ],
    });
    expect(text).toContain("凡人修仙");
    expect(text).toContain("第一卷 觉醒");
    expect(text).toContain("第一章 变故");
    expect(text).toContain("夜袭");
  });

  it("非法输入返回空串", () => {
    expect(structureToText(null)).toBe("");
    expect(structureToText("x")).toBe("");
  });
});

describe("checkOutlineCoverage", () => {
  const plot = "主角修仙进入宗门苦修三年，终于复仇雪恨，在宗门里一步步变强修仙";

  it("大纲覆盖了剧情关键词 → 命中率高", () => {
    const structure = {
      volumes: [
        {
          name: "第一卷 宗门修仙",
          summary: "主角进入宗门苦修三年",
          chapters: [{ title: "第一章 复仇", summary: "为了复仇雪恨" }],
        },
      ],
    };
    const r = checkOutlineCoverage(structure, plot);
    expect(r.total).toBeGreaterThan(0);
    expect(r.ratio).toBeGreaterThan(0.5);
  });

  it("大纲完全跑题 → 命中率低", () => {
    const structure = {
      volumes: [{ name: "第一卷 都市日常", summary: "上班吃饭睡觉", chapters: [] }],
    };
    const r = checkOutlineCoverage(structure, plot);
    expect(r.ratio).toBeLessThan(0.35);
    expect(r.missing.length).toBeGreaterThan(0);
  });

  it("剧情太短 → 无关键短语（不误报）", () => {
    const r = checkOutlineCoverage({ volumes: [] }, "短");
    expect(r.total).toBe(0);
    expect(coveragePercent(r)).toBe(100);
  });
});

function ratio(r: { ratio: number }): number {
  return r.ratio;
}
