/**
 * 词库管理的批量选择状态（纯逻辑）。
 *
 * 管理模式下每行前面多一个勾选框，底部显示"已选 N 项"并支持批量删除。
 * 这里把选择状态抽成纯函数，好测、也不怕组件里到处 setState。
 */

/** 词条的唯一标识（分类 + 空格 + 词，避免同名不同类互相干扰）。 */
export function wordKey(category: string, word: string): string {
  return `${category} ${word}`;
}

/** 勾选 / 取消勾选一个词条（返回新集合，不改原集合）。 */
export function toggleSelection(
  selected: ReadonlySet<string>,
  key: string,
): Set<string> {
  const next = new Set(selected);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  return next;
}

/** 全选（返回新集合）。 */
export function selectAll(keys: string[]): Set<string> {
  return new Set(keys);
}

/** 清空选择（返回空集合）。 */
export function clearSelection(): Set<string> {
  return new Set<string>();
}

/** 已选数量。 */
export function selectionCount(selected: ReadonlySet<string>): number {
  return selected.size;
}

/**
 * 把选中的 key 还原成后端要的 `{category, word}` 列表。
 *
 * key 是 `分类 空格 词条` 拼出来的，所以按第一个空格切开还原。
 * 认不出来的 key 直接跳过（不把脏数据发给后端）。
 */
export function selectedItems(
  selected: ReadonlySet<string>,
): { category: string; word: string }[] {
  const items: { category: string; word: string }[] = [];
  for (const key of selected) {
    const sep = key.indexOf(" ");
    if (sep <= 0) continue;
    const category = key.slice(0, sep);
    const word = key.slice(sep + 1);
    if (!category || !word) continue;
    items.push({ category, word });
  }
  return items;
}
