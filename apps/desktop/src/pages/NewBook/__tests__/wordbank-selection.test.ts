/**
 * 词库批量选择状态测试（纯逻辑）。
 *
 * 管理模式：每行前面一个勾选框 → 底部"已选 N 项" → 批量删除。
 */

import { describe, expect, it } from "vitest";
import {
  clearSelection,
  selectAll,
  selectedItems,
  selectionCount,
  toggleSelection,
  wordKey,
} from "../wordbank-selection";

describe("wordKey", () => {
  it("分类 + 空格 + 词（同词不同分类不冲突）", () => {
    expect(wordKey("themes", "逆袭")).not.toBe(wordKey("plots", "逆袭"));
  });
});

describe("toggleSelection", () => {
  it("勾上 / 取消", () => {
    const key = wordKey("themes", "逆袭");
    const on = toggleSelection(new Set<string>(), key);
    expect(on.has(key)).toBe(true);
    expect(selectionCount(on)).toBe(1);

    const off = toggleSelection(on, key);
    expect(off.has(key)).toBe(false);
    expect(selectionCount(off)).toBe(0);
  });

  it("不改原集合（返回新集合）", () => {
    const before = new Set<string>();
    const after = toggleSelection(before, "themes 逆袭");
    expect(before.size).toBe(0);
    expect(after.size).toBe(1);
  });
});

describe("selectAll / clearSelection", () => {
  it("全选与清空", () => {
    const all = selectAll(["themes 逆袭", "plots 草根"]);
    expect(selectionCount(all)).toBe(2);
    expect(selectionCount(clearSelection())).toBe(0);
  });
});

describe("selectedItems", () => {
  it("还原成后端要的 {category, word}", () => {
    const items = selectedItems(new Set(["themes 逆袭", "plots 草根"]));
    expect(items).toEqual([
      { category: "themes", word: "逆袭" },
      { category: "plots", word: "草根" },
    ]);
  });

  it("词里带空格也能还原（只按第一个空格切）", () => {
    const items = selectedItems(new Set(["themes dark lord"]));
    expect(items).toEqual([{ category: "themes", word: "dark lord" }]);
  });

  it("认不出来的 key 跳过", () => {
    expect(selectedItems(new Set(["垃圾key", "  ", ""]))).toEqual([]);
  });
});
