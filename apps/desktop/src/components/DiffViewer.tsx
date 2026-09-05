import { useMemo } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";
import { cn } from "@/lib/utils";

interface Props {
  /** unified diff 文本（来自后端 /versions/{id}/diff） */
  diff?: string;
  /** 直接传入 old/new（split 模式） */
  oldValue?: string;
  newValue?: string;
  /** split 模式：左右对比（true）或行内对比（false） */
  splitView?: boolean;
  className?: string;
  maxHeight?: number;
}

const DARK_COLORS = {
  background: "#0a0a0a",
  text: "#e5e7eb",
  addedBackground: "#022c22",
  addedColor: "#a7f3d0",
  removedBackground: "#450a0a",
  removedColor: "#fecaca",
  wordAddedBackground: "#059669",
  wordRemovedBackground: "#dc2626",
  addedGutterBackground: "#064e3b",
  removedGutterBackground: "#7f1d1d",
  gutterBackground: "#171717",
  gutterBackgroundDark: "#171717",
  highlightBackground: "#3f3f46",
  highlightGutterBackground: "#52525b",
  codeFoldGutterBackground: "#171717",
  codeFoldBackground: "#0a0a0a",
  emptyLineBackground: "#0a0a0a",
  gutterColor: "#a3a3a3",
  addedGutterColor: "#a7f3d0",
  removedGutterColor: "#fecaca",
  codeFoldContentColor: "#a3a3a3",
  diffViewerColor: "#e5e7eb",
  diffViewerTitleBackground: "#171717",
  diffViewerTitleColor: "#e5e7eb",
  diffViewerTitleBorderColor: "#262626",
};

const LIGHT_COLORS = {
  background: "#ffffff",
  text: "#1f2937",
  addedBackground: "#dcfce7",
  addedColor: "#15803d",
  removedBackground: "#fee2e2",
  removedColor: "#b91c1c",
  wordAddedBackground: "#22c55e",
  wordRemovedBackground: "#ef4444",
  addedGutterBackground: "#bbf7d0",
  removedGutterBackground: "#fecaca",
  gutterBackground: "#f9fafb",
  gutterBackgroundDark: "#f9fafb",
  highlightBackground: "#fef3c7",
  highlightGutterBackground: "#fde68a",
  codeFoldGutterBackground: "#f9fafb",
  codeFoldBackground: "#ffffff",
  emptyLineBackground: "#ffffff",
  gutterColor: "#6b7280",
  addedGutterColor: "#15803d",
  removedGutterColor: "#b91c1c",
  codeFoldContentColor: "#6b7280",
  diffViewerColor: "#1f2937",
  diffViewerTitleBackground: "#f9fafb",
  diffViewerTitleColor: "#1f2937",
  diffViewerTitleBorderColor: "#e5e7eb",
};

function useIsDark(): boolean {
  // 检测当前主题（基于 <html> 上的 .dark class）
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

function parseUnifiedDiff(diff: string): { oldText: string; newText: string } {
  /** 把 unified diff 文本粗略还原为 oldText / newText（仅用于纯文本模式升级到 split 模式时）*/
  const oldLines: string[] = [];
  const newLines: string[] = [];
  for (const line of diff.split("\n")) {
    if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) continue;
    if (line.startsWith("-")) oldLines.push(line.slice(1));
    else if (line.startsWith("+")) newLines.push(line.slice(1));
    else if (line.startsWith(" ")) {
      oldLines.push(line.slice(1));
      newLines.push(line.slice(1));
    }
  }
  return { oldText: oldLines.join("\n"), newText: newLines.join("\n") };
}

/** Unified / split diff 渲染（Phase 4.6 v2，使用 react-diff-viewer-continued）。
 *
 * 三种模式：
 * - 同时给 oldValue + newValue → split（默认）或 inline（splitView=false）渲染
 * - 只给 diff（unified 文本）→ 解析后用上面那种方式渲染
 * - 都没有 → 空状态
 */
export default function DiffViewer({
  diff,
  oldValue,
  newValue,
  splitView = true,
  className,
  maxHeight = 480,
}: Props) {
  const isDark = useIsDark();
  // 主题切换时强制重新渲染（深浅色变量更新）
  useMemo(() => [isDark], [isDark]);

  // 解析 unified diff → old/new
  let oldText = oldValue;
  let newText = newValue;
  if ((!oldText || !newText) && diff) {
    const parsed = parseUnifiedDiff(diff);
    oldText = parsed.oldText;
    newText = parsed.newText;
  }

  if (!oldText && !newText) {
    return (
      <p className="text-xs text-neutral-400 italic px-3 py-2">无差异</p>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-neutral-200 dark:border-neutral-800 overflow-auto",
        className,
      )}
      style={{ maxHeight }}
    >
      <ReactDiffViewer
        oldValue={oldText ?? ""}
        newValue={newText ?? ""}
        splitView={splitView}
        compareMethod={DiffMethod.WORDS}
        useDarkTheme={isDark}
        styles={{
          variables: { light: LIGHT_COLORS, dark: DARK_COLORS },
          contentText: { fontFamily: "ui-monospace, SFMono-Regular, monospace", fontSize: "0.75rem" },
        }}
        hideLineNumbers={false}
      />
    </div>
  );
}
