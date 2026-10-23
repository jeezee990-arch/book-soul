/**
 * 章节树（写作页左栏）。
 *
 * 后端 Chapter 没有"卷"字段（只有 chapter_number），所以这里按章节号平铺，
 * 不用设计稿里的卷分组 —— 避免前端造出后端不存在的数据结构。
 */

import { Plus } from "lucide-react";
import type { Chapter } from "@/lib/types";
import { CHAPTER_STATUS_DOT, CHAPTER_STATUS_LABEL } from "./types";
import { cn } from "@/lib/utils";

interface Props {
  chapters: Chapter[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCreate: () => void;
  loading: boolean;
}

export default function ChapterTree({
  chapters,
  selectedId,
  onSelect,
  onCreate,
  loading,
}: Props) {
  return (
    <aside className="flex w-[244px] shrink-0 flex-col border-r border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <span className="text-[10.5px] font-semibold tracking-[0.07em] text-neutral-400 uppercase">
          章节 {chapters.length > 0 ? `· ${chapters.length}` : ""}
        </span>
        <button
          type="button"
          onClick={onCreate}
          title="新建章节"
          aria-label="新建章节"
          className="grid h-6 w-6 place-items-center rounded-md text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-2.5">
        {loading ? (
          <div className="space-y-1 px-1.5 pt-1">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-8 animate-pulse rounded-md bg-neutral-100 dark:bg-neutral-800/60"
              />
            ))}
          </div>
        ) : chapters.length === 0 ? (
          <p className="px-2.5 py-4 text-center text-[11.5px] text-neutral-400">
            还没有章节
            <br />
            点右上角 + 新建
          </p>
        ) : (
          chapters.map((c) => {
            const on = c.id === selectedId;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => onSelect(c.id)}
                className={cn(
                  "mb-0.5 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition-colors",
                  on
                    ? "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300"
                    : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800",
                )}
              >
                <span
                  className={cn(
                    "w-[22px] shrink-0 font-mono text-[10.5px]",
                    on
                      ? "text-indigo-500"
                      : "text-neutral-400 dark:text-neutral-500",
                  )}
                >
                  {String(c.chapter_number).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  {c.title?.trim() || "（未命名）"}
                </span>
                <span
                  title={CHAPTER_STATUS_LABEL[c.status] ?? c.status}
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    CHAPTER_STATUS_DOT[c.status] ?? "bg-neutral-300 dark:bg-neutral-700",
                  )}
                />
                <span
                  className={cn(
                    "shrink-0 font-mono text-[10px] text-neutral-400",
                    !on && "opacity-0 group-hover:opacity-100",
                  )}
                >
                  {c.word_count > 0 ? `${(c.word_count / 1000).toFixed(1)}k` : ""}
                </span>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
