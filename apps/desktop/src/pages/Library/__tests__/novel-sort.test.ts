/**
 * 素材库「作品」排序逻辑的单元测试（2026-10-30）。
 *
 * 要锁住的是**两条顺序线**的一致性：
 * - 可见顺序（搜索 / 筛选 / 排序方式决定，用户看到的）
 * - 保存顺序（后端 sort_order，全局一份）
 *
 * 最容易写错的地方：只把**可见子集**发给后端 →
 * 隐藏的作品会被排到队尾，用户下次打开发现顺序全乱了。
 * 所以 `moveNovel` 的做法是：在可见列表里找邻居，在**全量**列表里交换两者位置。
 */

import { describe, expect, it } from "vitest";
import type { Novel } from "@/lib/types";
import {
  moveNovel,
  neighborId,
  sortNovels,
  swapInOrder,
} from "../novel-sort";

/** 造一个测试用作品。 */
function novel(
  id: number,
  name: string,
  extra: Partial<Novel> = {},
): Novel {
  return {
    id,
    name,
    genre: "修仙",
    style: null,
    description: null,
    status: "draft",
    outline_mode: null,
    file_path: null,
    imported: false,
    read_only: false,
    sort_order: id,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...extra,
  };
}

describe("sortNovels", () => {
  const items = [
    novel(1, "甲", { updated_at: "2026-01-01T00:00:00" }),
    novel(2, "乙", { updated_at: "2026-03-01T00:00:00" }),
    novel(3, "丙", { updated_at: "2026-02-01T00:00:00" }),
  ];

  it("手动顺序 = 保持传入顺序", () => {
    expect(sortNovels(items, "manual").map((n) => n.id)).toEqual([1, 2, 3]);
  });

  it("最近更新 = updated_at 倒序", () => {
    expect(sortNovels(items, "updated").map((n) => n.id)).toEqual([2, 3, 1]);
  });

  it("最近创建 = created_at 倒序", () => {
    const list = [
      novel(1, "甲", { created_at: "2026-01-01T00:00:00" }),
      novel(2, "乙", { created_at: "2026-05-01T00:00:00" }),
    ];
    expect(sortNovels(list, "created").map((n) => n.id)).toEqual([2, 1]);
  });

  it("字数最多 = 按字数倒序", () => {
    const list = sortNovels(items, "words", { 1: 10, 2: 300, 3: 100 });
    expect(list.map((n) => n.id)).toEqual([2, 3, 1]);
  });

  it("没有统计的作品按 0 字算", () => {
    const list = sortNovels(items, "words", { 2: 5 });
    expect(list[0].id).toBe(2);
  });

  it("按书名排序", () => {
    const list = sortNovels([novel(1, "丙"), novel(2, "甲")], "name");
    expect(list.map((n) => n.name)).toEqual(["丙", "甲"]);
  });

  it("不修改入参", () => {
    const before = items.map((n) => n.id);
    sortNovels(items, "updated");
    expect(items.map((n) => n.id)).toEqual(before);
  });
});

describe("swapInOrder", () => {
  it("交换两个 id 的位置", () => {
    expect(swapInOrder([1, 2, 3], 1, 3)).toEqual([3, 2, 1]);
  });

  it("不在列表里的 id 原样返回", () => {
    expect(swapInOrder([1, 2, 3], 1, 9)).toEqual([1, 2, 3]);
  });

  it("同一个 id 原样返回", () => {
    expect(swapInOrder([1, 2, 3], 2, 2)).toEqual([1, 2, 3]);
  });

  it("不修改入参", () => {
    const ids = [1, 2, 3];
    swapInOrder(ids, 1, 3);
    expect(ids).toEqual([1, 2, 3]);
  });
});

describe("neighborId", () => {
  it("向上找返回上一项", () => {
    expect(neighborId([1, 2, 3], 2, -1)).toBe(1);
  });

  it("向下找返回下一项", () => {
    expect(neighborId([1, 2, 3], 2, 1)).toBe(3);
  });

  it("第一项没有上一项", () => {
    expect(neighborId([1, 2, 3], 1, -1)).toBeNull();
  });

  it("最后一项没有下一项", () => {
    expect(neighborId([1, 2, 3], 3, 1)).toBeNull();
  });

  it("id 不在可见列表里 → null", () => {
    expect(neighborId([1, 2, 3], 9, -1)).toBeNull();
  });
});

describe("moveNovel", () => {
  it("上移：与可见列表的上一项交换", () => {
    // 全量 [1,2,3]，可见 [2,3]（比如被搜索过滤掉了 1）
    expect(moveNovel([1, 2, 3], [2, 3], 3, -1)).toEqual([1, 3, 2]);
  });

  it("下移：与可见列表的下一项交换", () => {
    expect(moveNovel([1, 2, 3], [1, 2, 3], 2, 1)).toEqual([1, 3, 2]);
  });

  it("已经在第一本 → null（不动）", () => {
    expect(moveNovel([1, 2, 3], [1, 2, 3], 1, -1)).toBeNull();
  });

  it("已经在最后一本 → null（不动）", () => {
    expect(moveNovel([1, 2, 3], [1, 2, 3], 3, 1)).toBeNull();
  });

  it("隐藏的作品位置不受影响（只交换两本）", () => {
    // 全量 [1,2,3,4]，可见 [3,4]；上移 4 → 与 3 交换，1/2 不动
    expect(moveNovel([1, 2, 3, 4], [3, 4], 4, -1)).toEqual([1, 2, 4, 3]);
  });
});
