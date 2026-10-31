/**
 * 素材库「作品」Tab 的排序逻辑（2026-10-30）。
 *
 * 为什么要抽成纯函数
 * ------------------
 * 排序有两条线，容易写错：
 *
 * 1. **看得到的顺序**（搜索 / 状态筛选 / 排序方式共同决定）
 * 2. **存下来的顺序**（后端 ``sort_order``，全局一份）
 *
 * "上移 / 下移"必须同时改对这两条线：用户看到的是筛选后的列表，
 * 但保存的必须是**全量**顺序 —— 只把可见子集发给后端的话，
 * 隐藏的作品会被排到队尾，用户下次打开发现顺序全乱了。
 *
 * 所以这里的做法是：**在可见列表里找邻居 → 在全量列表里交换两者的位置**。
 * 这样既符合用户看到的顺序，又不动其它作品的相对次序。
 */

import type { Novel } from "@/lib/types";

/** 排序方式。 */
export type NovelSortKey =
  /** 手动顺序（后端 sort_order，用户自己排的） */
  | "manual"
  /** 最近更新 */
  | "updated"
  /** 最近创建 */
  | "created"
  /** 字数最多 */
  | "words"
  /** 书名（拼音序） */
  | "name";

/** 排序下拉的选项（顺序即展示顺序）。 */
export const NOVEL_SORT_OPTIONS: { value: NovelSortKey; label: string }[] = [
  { value: "manual", label: "手动顺序" },
  { value: "updated", label: "最近更新" },
  { value: "created", label: "最近创建" },
  { value: "words", label: "字数最多" },
  { value: "name", label: "按书名" },
];

/** 每部作品的字数（从章节统计汇总；没有统计的按 0 算）。 */
export type WordCountMap = Record<number, number>;

/**
 * 按指定方式排序。
 *
 * ⚠️ 不修改入参（返回新数组）。
 *
 * @param items - 作品列表（通常已经是搜索/筛选后的可见列表）
 * @param key - 排序方式
 * @param words - id → 字数（只有 `words` 排序用得上）
 * @returns 排好序的新数组
 */
export function sortNovels(
  items: Novel[],
  key: NovelSortKey,
  words: WordCountMap = {},
): Novel[] {
  const list = [...items];
  switch (key) {
    case "updated":
      return list.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    case "created":
      return list.sort((a, b) => b.created_at.localeCompare(a.created_at));
    case "words":
      return list.sort(
        (a, b) => (words[b.id] ?? 0) - (words[a.id] ?? 0),
      );
    case "name":
      return list.sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"));
    case "manual":
    default:
      // 手动顺序 = 后端返回的顺序（已按 sort_order 排好），原样保留
      return list;
  }
}

/**
 * 在全量 id 顺序里交换两个作品的位置。
 *
 * @param ids - 全量 id 顺序（当前保存的顺序）
 * @param a - 要移动的 id
 * @param b - 与它交换位置的 id
 * @returns 新顺序（入参不被修改）；任一 id 不在列表里时原样返回
 */
export function swapInOrder(
  ids: number[],
  a: number,
  b: number,
): number[] {
  const ia = ids.indexOf(a);
  const ib = ids.indexOf(b);
  if (ia < 0 || ib < 0 || ia === ib) return ids;
  const next = [...ids];
  next[ia] = b;
  next[ib] = a;
  return next;
}

/**
 * 在**可见列表**里找上/下邻居。
 *
 * @param visibleIds - 可见作品的 id 顺序（已排序）
 * @param id - 目标作品 id
 * @param delta - -1 向上找，+1 向下找
 * @returns 邻居 id；已经在边界上时返回 null
 */
export function neighborId(
  visibleIds: number[],
  id: number,
  delta: -1 | 1,
): number | null {
  const idx = visibleIds.indexOf(id);
  if (idx < 0) return null;
  const next = visibleIds[idx + delta];
  return next ?? null;
}

/**
 * 移动作品后的新全量顺序。
 *
 * @param allIds - 全量 id 顺序（当前保存的顺序）
 * @param visibleIds - 可见 id 顺序（已排序）
 * @param id - 要移动的作品 id
 * @param delta - -1 上移，+1 下移
 * @returns 新顺序；已经在边界上时返回 null（表示"不用动"）
 */
export function moveNovel(
  allIds: number[],
  visibleIds: number[],
  id: number,
  delta: -1 | 1,
): number[] | null {
  const neighbor = neighborId(visibleIds, id, delta);
  if (neighbor === null) return null;
  return swapInOrder(allIds, id, neighbor);
}
