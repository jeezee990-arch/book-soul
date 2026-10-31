/**
 * 作品卡片（素材库 · 作品 Tab）。
 *
 * 2026-10-30 从 LibraryList 里拆出来：作品列表页已经接近 500 行上限，
 * 而卡片本身要管的事不少（封面 / 标题 / 统计 / 进度 / 悬停操作 / 右键 / 键盘）。
 *
 * 三种打开管理菜单的途径（同一个 NovelContextMenu）：
 * 1. **鼠标右键**卡片
 * 2. **点「⋯」按钮**（悬停出现）—— 右键菜单本身是隐形的，必须给一个看得见的入口
 * 3. **键盘**：聚焦卡片后按 `Shift+F10` 或 `ContextMenu` 键
 */

import { FileDown, MoreHorizontal, PenLine } from "lucide-react";
import type { Novel } from "@/lib/types";
import { cn } from "@/lib/utils";

/** 作品的章节统计（由列表页异步补齐后传入）。 */
export interface NovelStat {
  words: number;
  chapters: number;
  written: number;
}

/** 没有统计信息时的占位。 */
export const EMPTY_STAT: NovelStat = { words: 0, chapters: 0, written: 0 };

/** 导出格式。 */
export type ExportFormat = "md" | "html" | "docx";

interface Props {
  novel: Novel;
  stat: NovelStat;
  /** 打开作品详情。 */
  onOpen: (n: Novel) => void;
  /** 继续写（切到写作页）。 */
  onContinue: (n: Novel) => void;
  /** 导出。 */
  onExport: (n: Novel, format: ExportFormat) => void;
  /** 在指定坐标处打开管理菜单。 */
  onMenu: (n: Novel, x: number, y: number) => void;
}

/** 状态 → 圆点颜色 + 中文。 */
function statusMeta(novel: Novel): { dot: string; label: string } {
  if (novel.imported) return { dot: "bg-neutral-400", label: "已导入" };
  switch (novel.status) {
    case "draft":
      return { dot: "bg-neutral-400", label: "草稿" };
    case "writing":
    case "serializing":
      return { dot: "bg-violet-500", label: "连载中" };
    case "done":
    case "finished":
      return { dot: "bg-emerald-500", label: "已完成" };
    default:
      return { dot: "bg-indigo-500", label: novel.status || "进行中" };
  }
}

/**
 * 作品卡片。
 *
 * @param props - 组件属性
 */
export default function NovelCard({
  novel,
  stat,
  onOpen,
  onContinue,
  onExport,
  onMenu,
}: Props) {
  const meta = statusMeta(novel);
  const progress = stat.chapters
    ? Math.round((stat.written / stat.chapters) * 100)
    : 0;

  /** 鼠标右键 → 在鼠标位置打开菜单。 */
  function handleContextMenu(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    onMenu(novel, e.clientX, e.clientY);
  }

  /**
   * 键盘打开菜单（无障碍路径）。
   *
   * 标准绑定是 **Shift+F10** 或 **ContextMenu 键**。
   */
  function handleCardKeyDown(e: React.KeyboardEvent) {
    const isContextKey = e.key === "ContextMenu" || (e.shiftKey && e.key === "F10");
    if (!isContextKey) return;
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    onMenu(novel, rect.left + 24, rect.top + 24);
  }

  /** 「⋯」按钮 → 在按钮下方打开同一个菜单。 */
  function handleMoreClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    onMenu(novel, rect.left, rect.bottom + 4);
  }

  return (
    <div
      onContextMenu={handleContextMenu}
      className="group relative overflow-hidden rounded-xl border border-neutral-200 bg-white transition-all hover:-translate-y-px hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700"
    >
      <button
        type="button"
        onClick={() => onOpen(novel)}
        onKeyDown={handleCardKeyDown}
        className="block w-full text-left"
      >
        <div
          className="grid h-[98px] place-items-center"
          style={{
            background: `linear-gradient(150deg, hsl(${(novel.id * 47) % 360} 32% 26%), hsl(${(novel.id * 83) % 360} 38% 17%))`,
          }}
        >
          {/* 封面用书名首字：跨平台渲染一致，也不像 emoji 那样抢视觉 */}
          <span className="text-[36px] font-semibold tracking-tight text-white/85">
            {(novel.name || "书").trim().charAt(0)}
          </span>
        </div>
        <div className="p-3">
          <div className="flex items-center gap-1.5">
            <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
            <span className="truncate text-[13px] font-semibold">{novel.name}</span>
          </div>
          <div className="mt-1.5 flex gap-2 text-[11px] text-neutral-400">
            <span>{novel.genre}</span>
            <span className="font-mono">{stat.words.toLocaleString()} 字</span>
            <span>
              {stat.written}/{stat.chapters} 章
            </span>
          </div>
          <div className="mt-2.5 h-[3px] overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
            <i
              className="block h-full rounded-full bg-indigo-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </button>

      {/* 悬停操作 */}
      <div className="absolute top-2.5 right-2.5 flex items-center gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        <button
          type="button"
          onClick={() => onContinue(novel)}
          title="继续写"
          className="inline-flex h-6 items-center gap-1 rounded-md bg-white/90 px-2 text-[10.5px] text-neutral-700 shadow-sm backdrop-blur hover:bg-white dark:bg-neutral-800/90 dark:text-neutral-200"
        >
          <PenLine className="h-3 w-3" />
          继续写
        </button>
        <button
          type="button"
          onClick={handleMoreClick}
          title="更多操作（右键菜单）"
          aria-label={`《${novel.name}》更多操作`}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-white/90 text-neutral-600 shadow-sm backdrop-blur hover:bg-white dark:bg-neutral-800/90 dark:text-neutral-300"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex items-center gap-0.5 border-t border-neutral-200/70 px-2 py-1 dark:border-neutral-800/70">
        {(["md", "html", "docx"] as const).map((fmt) => (
          <button
            key={fmt}
            type="button"
            onClick={() => onExport(novel, fmt)}
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[10px] text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
          >
            <FileDown className="h-2.5 w-2.5" />
            {fmt === "docx" ? "Word" : fmt.toUpperCase()}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-neutral-400">{meta.label}</span>
      </div>
    </div>
  );
}
