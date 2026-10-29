/**
 * 词库管理纯逻辑测试（导入预解析 + 分类标签）。
 *
 * 规则必须与后端 ``server/src/services/wordbank_importer.py`` 一致 ——
 * 后端才是权威，前端这份只用于导入前的预览。
 */

import { describe, expect, it } from "vitest";
import {
  CATEGORY_LABELS,
  categoryLabel,
  genreLabel,
  parseImportText,
  resolveCategory,
  summarizeImport,
} from "../wordbank-parse";

const CATEGORIES = ["themes", "characters", "plots", "scenes", "items"];

function parse(text: string, defaultCategory = "themes") {
  return parseImportText(text, defaultCategory, CATEGORIES);
}

describe("categoryLabel", () => {
  it("分类 key 转中文标签", () => {
    expect(categoryLabel("themes")).toBe("主题");
    expect(categoryLabel("characters")).toBe("人物");
    expect(categoryLabel("plots")).toBe("情节");
    expect(categoryLabel("scenes")).toBe("场景");
    expect(categoryLabel("items")).toBe("物品");
  });

  it("认不出来的分类原样返回", () => {
    expect(categoryLabel("weird")).toBe("weird");
  });

  it("五个分类都有标签", () => {
    for (const key of CATEGORIES) {
      expect(CATEGORY_LABELS[key]).toBeTruthy();
    }
  });
});

describe("genreLabel", () => {
  it("优先用后端返回的板块名", () => {
    expect(genreLabel("xiuxian", "修仙")).toBe("修仙");
  });

  it("没有板块名时回落 id", () => {
    expect(genreLabel("xiuxian")).toBe("xiuxian");
    expect(genreLabel("xiuxian", "  ")).toBe("xiuxian");
  });
});

describe("resolveCategory", () => {
  it("英文 key / 中文别名都能认", () => {
    expect(resolveCategory("themes", CATEGORIES)).toBe("themes");
    expect(resolveCategory("THEMES", CATEGORIES)).toBe("themes");
    expect(resolveCategory("主题", CATEGORIES)).toBe("themes");
    expect(resolveCategory("剧情", CATEGORIES)).toBe("plots");
  });

  it("当前板块没这个分类 → 不认", () => {
    expect(resolveCategory("items", ["themes"])).toBeNull();
    expect(resolveCategory("法宝", ["themes"])).toBeNull();
  });

  it("空串 / 乱写 → 不认", () => {
    expect(resolveCategory("", CATEGORIES)).toBeNull();
    expect(resolveCategory("瞎写", CATEGORIES)).toBeNull();
  });
});

describe("parseImportText", () => {
  it("空文本 → 没有词也没有问题", () => {
    const r = parse("");
    expect(r.words).toEqual([]);
    expect(r.issues).toEqual([]);
  });

  it("换行分隔", () => {
    const r = parse("逆袭\n草根");
    expect(r.words.map((w) => w.word)).toEqual(["逆袭", "草根"]);
    expect(r.words[0].category).toBe("themes");
  });

  it("逗号 / 顿号 / 中文逗号 / 分号 / 竖线 分隔", () => {
    const r = parse("a,b，c、d;e；f|g");
    expect(r.words.map((w) => w.word)).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
  });

  it("空格不当分隔符", () => {
    const r = parse("dark lord");
    expect(r.words.map((w) => w.word)).toEqual(["dark lord"]);
  });

  it("注释行与空行忽略", () => {
    const r = parse("# 注释\n\n// 注释\n逆袭");
    expect(r.words.map((w) => w.word)).toEqual(["逆袭"]);
    expect(r.issues).toEqual([]);
  });

  it("行首分类前缀作用于整行", () => {
    const r = parse("themes:逆袭,草根");
    expect(r.words.map((w) => `${w.category}/${w.word}`)).toEqual([
      "themes/逆袭",
      "themes/草根",
    ]);
  });

  it("中文别名分类前缀", () => {
    const r = parse("人物：师姐");
    expect(r.words[0].category).toBe("characters");
    expect(r.words[0].word).toBe("师姐");
  });

  it("词条自带前缀只影响那一个词", () => {
    const r = parse("themes:逆袭,characters:师姐");
    expect(r.words.map((w) => `${w.category}/${w.word}`)).toEqual([
      "themes/逆袭",
      "characters/师姐",
    ]);
  });

  it("认不出来的分类 → 逐行报错", () => {
    const r = parse("未知分类:词条");
    expect(r.words).toEqual([]);
    expect(r.issues).toHaveLength(1);
    expect(r.issues[0].lineNo).toBe(1);
    expect(r.issues[0].reason).toContain("未知分类");
  });

  it("中间某个词的前缀认不出来 → 只报那一个词", () => {
    const r = parse("逆袭,瞎写:词");
    expect(r.words.map((w) => w.word)).toEqual(["逆袭"]);
    expect(r.issues).toHaveLength(1);
  });

  it("过长词条报错", () => {
    const r = parse("词".repeat(100));
    expect(r.words).toEqual([]);
    expect(r.issues[0].reason).toContain("过长");
  });

  it("批次内重复被去掉", () => {
    const r = parse("逆袭\n逆袭");
    expect(r.words).toHaveLength(1);
    expect(r.duplicates).toBe(1);
  });

  it("同词不同分类都保留", () => {
    const r = parse("themes:逆袭\ncharacters:逆袭");
    expect(r.words).toHaveLength(2);
    expect(r.duplicates).toBe(0);
  });

  it("默认分类生效", () => {
    const r = parse("逆袭", "plots");
    expect(r.words[0].category).toBe("plots");
  });

  it("保留行号", () => {
    const r = parse("\n\n逆袭");
    expect(r.words[0].lineNo).toBe(3);
  });
});

describe("summarizeImport", () => {
  it("摘要含词条数 / 重复数 / 问题行数", () => {
    const r = parse("逆袭\n逆袭\n瞎写:词");
    const s = summarizeImport(r);
    expect(s).toContain("1 个词条");
    expect(s).toContain("1 个重复");
    expect(s).toContain("1 行有问题");
  });
});
