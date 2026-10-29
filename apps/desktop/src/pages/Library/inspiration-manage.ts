/**
 * 素材库管理的纯逻辑（2026-10-29）。
 *
 * 为什么要单独抽出来：右键菜单 / 批量管理 / 长按拖动排序三块交互，
 * 真正容易写错的是**顺序计算**和**标题派生**——
 * 它们是纯函数，抽出来就能用 vitest 直接测，不用起 DOM。
 *
 * 约定：
 * - 置顶项永远排在列表最前（后端 `pinned DESC, sort_order ASC, created_at DESC`）。
 *   所以拖拽**不跨组**：置顶项只在置顶组里挪，普通项只在普通组里挪。
 *   否则用户把普通项拖到置顶项上面，界面纹丝不动 —— 用户会以为拖坏了。
 */

/** 派生摘要标签的最大长度。 */
const DERIVED_TITLE_MAX = 40;

/** 空内容时的占位文案。 */
const EMPTY_LABEL = "（空）";

/**
 * 截断并补省略号。
 *
 * @param text - 原始文本
 * @param max - 最大长度（不含省略号）
 */
function truncate(text: string, max: number = DERIVED_TITLE_MAX): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max)}…`;
}

/**
 * 派生素材的显示标题。
 *
 * 优先用用户自定义的 `title`；没有就用 content 摘要兜底：
 * - keyword → words 拼接
 * - plot → summary
 * - snippet / note → text
 * - image → description
 *
 * @param inspiration - 素材条目
 * @returns 可直接显示的标题
 */
export function deriveInspirationTitle(inspiration: {
  title?: string | null;
  type: string;
  content?: Record<string, unknown> | null;
}): string {
  const custom = inspiration.title?.trim();
  if (custom) return custom;

  const content = inspiration.content ?? {};
  const derived = deriveFromContent(inspiration.type, content);
  return derived || EMPTY_LABEL;
}

/**
 * 按 type 从 content 派生摘要文本。
 *
 * @param type - 灵感类型
 * @param content - content dict
 * @returns 摘要文本（内容缺失时返回空串）
 */
function deriveFromContent(type: string, content: Record<string, unknown>): string {
  switch (type) {
    case "keyword": {
      const words = Array.isArray(content.words)
        ? (content.words as unknown[]).filter(
            (w): w is string => typeof w === "string",
          )
        : [];
      return words.length ? words.join(" · ") : "";
    }
    case "plot":
      return truncate(asText(content.summary));
    case "snippet":
    case "note":
      return truncate(asText(content.text));
    case "image":
      return truncate(asText(content.description));
    default:
      return truncate(JSON.stringify(content));
  }
}

/**
 * 把 content 里的字段安全地取成字符串。
 *
 * @param value - 任意值
 * @returns 字符串（缺失或类型不对时返回空串）
 */
function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * 切换置顶状态。
 *
 * @param pinned - 当前置顶状态
 * @returns 切换后的置顶状态
 */
export function togglePinned(pinned: boolean): boolean {
  return !pinned;
}

/**
 * 计算拖拽落点在**结果数组**里的最终下标。
 *
 * 结果数组 = 原数组去掉被拖的项，再把它插回去。
 * 所以落点下标要在「去掉被拖项之后」的数组里算。
 *
 * @param ids - 当前显示顺序的 id 数组
 * @param draggedId - 被拖动的 id
 * @param hoveredId - 鼠标当前悬停的 id
 * @param placeAfter - true 表示落在 hovered 之后，false 表示落在之前
 * @returns 最终下标；参数无效时返回 null
 */
export function computeDropIndex(
  ids: number[],
  draggedId: number,
  hoveredId: number,
  placeAfter: boolean,
): number | null {
  const from = ids.indexOf(draggedId);
  const hovered = ids.indexOf(hoveredId);
  if (from < 0 || hovered < 0 || hovered === from) return null;

  const rest = ids.filter((id) => id !== draggedId);
  const hoveredPos = rest.indexOf(hoveredId);
  const insertAt = placeAfter ? hoveredPos + 1 : hoveredPos;
  return Math.max(0, Math.min(insertAt, rest.length));
}

/**
 * 把落点限制在「同一组」内。
 *
 * 置顶组永远在最前，跨组拖拽会让界面看起来没动 —— 所以限制掉。
 *
 * @param ids - 当前显示顺序的 id 数组
 * @param isPinned - 判断某 id 是否置顶
 * @param draggedId - 被拖动的 id
 * @param finalIndex - 未经限制的最终下标
 * @returns 限制后的最终下标
 */
export function clampDropIndex(
  ids: number[],
  isPinned: (id: number) => boolean,
  draggedId: number,
  finalIndex: number,
): number {
  const pinnedCount = ids.filter(isPinned).length;
  const draggedPinned = isPinned(draggedId);
  const min = draggedPinned ? 0 : pinnedCount;
  const max = draggedPinned ? Math.max(0, pinnedCount - 1) : ids.length - 1;
  return Math.max(min, Math.min(finalIndex, max));
}

/**
 * 把被拖项移动到指定下标。
 *
 * @param ids - 当前顺序
 * @param draggedId - 被拖动的 id
 * @param finalIndex - 结果数组里的最终下标
 * @returns 新顺序（入参不被修改）；找不到被拖项时原样返回
 */
export function moveToIndex(
  ids: number[],
  draggedId: number,
  finalIndex: number,
): number[] {
  if (!ids.includes(draggedId)) return ids;
  const rest = ids.filter((id) => id !== draggedId);
  const clamped = Math.max(0, Math.min(finalIndex, rest.length));
  rest.splice(clamped, 0, draggedId);
  return rest;
}

/**
 * 拖拽结束后算出新的 id 顺序。
 *
 * @param ids - 当前显示顺序
 * @param isPinned - 判断某 id 是否置顶
 * @param draggedId - 被拖动的 id
 * @param hoveredId - 落点所在条目
 * @param placeAfter - 是否落在 hovered 之后
 * @returns 新的 id 顺序；落点无效时返回 null
 */
export function computeReorderedIds(
  ids: number[],
  isPinned: (id: number) => boolean,
  draggedId: number,
  hoveredId: number,
  placeAfter: boolean,
): number[] | null {
  const dropIndex = computeDropIndex(ids, draggedId, hoveredId, placeAfter);
  if (dropIndex === null) return null;
  const clamped = clampDropIndex(ids, isPinned, draggedId, dropIndex);
  return moveToIndex(ids, draggedId, clamped);
}

/**
 * 勾选状态切换（管理模式的批量选择）。
 *
 * @param selected - 当前已选 id 集合
 * @param id - 要切换的 id
 * @returns 新的已选集合（不修改入参）
 */
export function toggleSelected(
  selected: ReadonlySet<number>,
  id: number,
): Set<number> {
  const next = new Set(selected);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}

/**
 * 重命名提交时的**载荷判定**。
 *
 * ⚠️ 2026-10-29 评审事故：以前取消 / ESC / 点遮罩都传空串，
 *    等于"保存空标题" → 用户自定义标题被**静默清空**（点取消反而丢数据）。
 *    现在三态分明：
 *    - `null` → 用户取消 → 返回 null（**不发请求**）
 *    - `""` → 保存但清空标题（回落到自动摘要）
 *    - 其他 → 保存新标题
 *
 * @param title - 对话框回传的值（null = 取消）
 * @returns 要 PATCH 的载荷；取消时返回 null
 */
export function resolveRenamePayload(
  title: string | null,
): { title: string | null } | null {
  if (title === null) return null;
  return { title: title.trim() || null };
}
