/**
 * 写作页共享类型。
 */

/** 右栏上下文面板的 5 个 Tab。 */
export type PanelTab =
  | "generate"
  | "rewrite"
  | "characters"
  | "outline"
  | "versions";

/** 章节状态 → 展示用的小圆点颜色（与章节树一致）。 */
export const CHAPTER_STATUS_DOT: Record<string, string> = {
  outline: "bg-amber-500",
  drafting: "bg-violet-500",
  written: "bg-sky-500",
  final: "bg-emerald-500",
};

/** 章节状态 → 中文标签。 */
export const CHAPTER_STATUS_LABEL: Record<string, string> = {
  outline: "大纲",
  drafting: "草稿",
  written: "已写",
  final: "完稿",
};
