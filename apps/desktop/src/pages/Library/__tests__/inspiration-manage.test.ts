/**
 * 素材库管理纯逻辑测试（2026-10-29）。
 *
 * 覆盖三块最容易写错的地方：
 * - 派生标题（title 为空时从 content 兜底）
 * - 拖拽后的新顺序计算（含"置顶不跨组"的钳制）
 * - 置顶 / 勾选的 toggle
 */

import { describe, expect, it } from "vitest";
import {
  clampDropIndex,
  computeDropIndex,
  computeReorderedIds,
  deriveInspirationTitle,
  moveToIndex,
  togglePinned,
  toggleSelected,
} from "../inspiration-manage";

describe("deriveInspirationTitle", () => {
  it("优先用用户自定义的 title", () => {
    expect(
      deriveInspirationTitle({
        title: "剑与霜",
        type: "note",
        content: { text: "别的内容" },
      }),
    ).toBe("剑与霜");
  });

  it("title 只有空白字符时也退回派生", () => {
    expect(
      deriveInspirationTitle({ title: "   ", type: "note", content: { text: "abc" } }),
    ).toBe("abc");
  });

  it("keyword 拼接 words", () => {
    expect(
      deriveInspirationTitle({
        title: null,
        type: "keyword",
        content: { words: ["修仙", "废柴"] },
      }),
    ).toBe("修仙 · 废柴");
  });

  it("note / snippet 取 text 前 40 字", () => {
    const long = "字".repeat(80);
    const out = deriveInspirationTitle({
      title: null,
      type: "note",
      content: { text: long },
    });
    expect(out).toHaveLength(41); // 40 字 + 省略号
    expect(out.endsWith("…")).toBe(true);
  });

  it("plot 取 summary，image 取 description", () => {
    expect(
      deriveInspirationTitle({
        title: null,
        type: "plot",
        content: { summary: "主角身世之谜" },
      }),
    ).toBe("主角身世之谜");
    expect(
      deriveInspirationTitle({
        title: null,
        type: "image",
        content: { description: "云海之巅" },
      }),
    ).toBe("云海之巅");
  });

  it("内容缺失时给占位文案", () => {
    expect(
      deriveInspirationTitle({ title: null, type: "note", content: {} }),
    ).toBe("（空）");
    expect(
      deriveInspirationTitle({
        title: null,
        type: "keyword",
        content: { words: [] },
      }),
    ).toBe("（空）");
  });

  it("words 里混了非字符串要过滤掉", () => {
    expect(
      deriveInspirationTitle({
        title: null,
        type: "keyword",
        content: { words: ["修仙", 123, null] },
      }),
    ).toBe("修仙");
  });
});

describe("togglePinned", () => {
  it("置顶状态取反", () => {
    expect(togglePinned(false)).toBe(true);
    expect(togglePinned(true)).toBe(false);
  });
});

describe("toggleSelected", () => {
  it("未选中 → 选中", () => {
    const next = toggleSelected(new Set([1]), 2);
    expect(next.has(2)).toBe(true);
    expect(next.has(1)).toBe(true);
  });

  it("已选中 → 取消", () => {
    const next = toggleSelected(new Set([1, 2]), 2);
    expect(next.has(2)).toBe(false);
    expect(next.size).toBe(1);
  });

  it("不修改入参", () => {
    const before = new Set([1]);
    toggleSelected(before, 2);
    expect(before.size).toBe(1);
  });
});

describe("computeDropIndex", () => {
  const ids = [1, 2, 3, 4];

  it("落在悬停项之前", () => {
    // 结果数组 = [2,3,4]，3 在下标 1 → 插到 1
    expect(computeDropIndex(ids, 1, 3, false)).toBe(1);
  });

  it("落在悬停项之后", () => {
    expect(computeDropIndex(ids, 1, 3, true)).toBe(2);
  });

  it("悬停项就是自己 → 无效", () => {
    expect(computeDropIndex(ids, 2, 2, false)).toBeNull();
  });

  it("id 不在列表里 → 无效", () => {
    expect(computeDropIndex(ids, 99, 2, false)).toBeNull();
    expect(computeDropIndex(ids, 1, 99, false)).toBeNull();
  });
});

describe("clampDropIndex", () => {
  const never = () => false;
  const always = () => true;

  it("普通项不能插到置顶项前面", () => {
    // [置顶, 置顶, 普通, 普通]
    const ids = [1, 2, 3, 4];
    const isPinned = (id: number) => id === 1 || id === 2;
    expect(clampDropIndex(ids, isPinned, 3, 0)).toBe(2);
  });

  it("置顶项只能在置顶组内挪", () => {
    const ids = [1, 2, 3, 4];
    const isPinned = (id: number) => id === 1 || id === 2;
    expect(clampDropIndex(ids, isPinned, 1, 3)).toBe(1);
  });

  it("没有置顶项时钳制不生效", () => {
    expect(clampDropIndex([1, 2, 3], never, 1, 0)).toBe(0);
    expect(clampDropIndex([1, 2, 3], never, 1, 9)).toBe(2);
  });

  it("全是置顶项时普通组为空也不会越界", () => {
    expect(clampDropIndex([1, 2], always, 1, 5)).toBe(1);
  });
});

describe("moveToIndex", () => {
  it("把项移到指定下标", () => {
    expect(moveToIndex([1, 2, 3, 4], 1, 2)).toEqual([2, 3, 1, 4]);
    expect(moveToIndex([1, 2, 3, 4], 4, 0)).toEqual([4, 1, 2, 3]);
  });

  it("下标越界时夹到边界", () => {
    expect(moveToIndex([1, 2, 3], 1, 99)).toEqual([2, 3, 1]);
    expect(moveToIndex([1, 2, 3], 3, -5)).toEqual([3, 1, 2]);
  });

  it("找不到被拖项时原样返回", () => {
    const ids = [1, 2, 3];
    expect(moveToIndex(ids, 99, 0)).toBe(ids);
  });

  it("不修改入参", () => {
    const ids = [1, 2, 3];
    moveToIndex(ids, 1, 2);
    expect(ids).toEqual([1, 2, 3]);
  });
});

describe("computeReorderedIds", () => {
  it("把第 1 项拖到第 3 项之后", () => {
    const ids = [1, 2, 3, 4];
    // 落在 3 的下半区 → 插到 3 之后、4 之前
    expect(computeReorderedIds(ids, () => false, 1, 3, true)).toEqual([
      2, 3, 1, 4,
    ]);
  });

  it("把最后一项拖到最前", () => {
    const ids = [1, 2, 3, 4];
    expect(computeReorderedIds(ids, () => false, 4, 1, false)).toEqual([
      4, 1, 2, 3,
    ]);
  });

  it("置顶项只在置顶组内重排", () => {
    // [置顶A, 置顶B, 普通C, 普通D]
    const ids = [1, 2, 3, 4];
    const isPinned = (id: number) => id === 1 || id === 2;
    // 想把置顶A拖到普通D之后 → 被钳回置顶组内
    expect(computeReorderedIds(ids, isPinned, 1, 4, true)).toEqual([2, 1, 3, 4]);
  });

  it("普通项不能跨到置顶组前面", () => {
    const ids = [1, 2, 3, 4];
    const isPinned = (id: number) => id === 1 || id === 2;
    // 想把普通C拖到置顶A之前 → 钳到置顶组之后
    expect(computeReorderedIds(ids, isPinned, 3, 1, false)).toEqual([1, 2, 3, 4]);
  });

  it("落点无效时返回 null", () => {
    expect(computeReorderedIds([1, 2], () => false, 1, 1, false)).toBeNull();
  });
});
