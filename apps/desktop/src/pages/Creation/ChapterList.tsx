import { Plus, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Chapter } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  chapters: Chapter[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCreate: () => void;
  loading: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  outline: "大纲",
  drafting: "草稿",
  written: "已写",
  final: "完稿",
};

const STATUS_TONE: Record<string, string> = {
  outline: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300",
  drafting: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
  written: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200",
  final: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200",
};

/** 章节列表（Phase 4.1）。左侧边栏 + 新建按钮。 */
export default function ChapterList({
  chapters,
  selectedId,
  onSelect,
  onCreate,
  loading,
}: Props) {
  if (loading) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-neutral-500">
          章节 · {chapters.length}
        </span>
        <Button size="sm" variant="outline" onClick={onCreate} className="h-7 px-2 text-xs">
          <Plus className="mr-1 h-3 w-3" />
          新建章节
        </Button>
      </div>
      <div className="space-y-1 max-h-[560px] overflow-y-auto pr-1">
        {chapters.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-neutral-400">暂无章节</p>
        ) : (
          chapters.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={cn(
                "w-full text-left rounded-md border px-3 py-2 text-sm transition-colors",
                c.id === selectedId
                  ? "border-neutral-900 dark:border-neutral-100 bg-neutral-50 dark:bg-neutral-900"
                  : "border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900/50",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 font-medium truncate">
                  <FileText className="h-3 w-3 shrink-0 text-neutral-400" />
                  第 {c.chapter_number} 章 · {c.title ?? "（未命名）"}
                </span>
                <span
                  className={cn(
                    "shrink-0 rounded px-1.5 py-0.5 text-[10px]",
                    STATUS_TONE[c.status] ?? STATUS_TONE.outline,
                  )}
                >
                  {STATUS_LABEL[c.status] ?? c.status}
                </span>
              </div>
              <div className="mt-0.5 flex items-center justify-between text-[10px] text-neutral-500">
                <span className="truncate">
                  {c.outline ? c.outline.slice(0, 40) + (c.outline.length > 40 ? "…" : "") : "—"}
                </span>
                <span className="ml-2 shrink-0">{c.word_count.toLocaleString()} 字</span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
