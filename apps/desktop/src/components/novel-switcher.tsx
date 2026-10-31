/**
 * 顶栏作品切换器。
 *
 * 这是**全局唯一**的作品选择入口 —— 切换后写入 workspaceStore，
 * 写作页、人物卡、大纲全部跟着切换，不再有第二份下拉框。
 */

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Plus } from "lucide-react";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

/** 作品封面色：按 id 取色，同一本书颜色稳定。 */
function coverStyle(id: number): string {
  const palette = [
    "linear-gradient(150deg,#4f46e5,#8b5cf6)",
    "linear-gradient(150deg,#0ea5e9,#6366f1)",
    "linear-gradient(150deg,#f43f5e,#8b5cf6)",
    "linear-gradient(150deg,#10b981,#0ea5e9)",
    "linear-gradient(150deg,#f59e0b,#f43f5e)",
  ];
  return palette[id % palette.length];
}

export default function NovelSwitcher() {
  const navigate = useNavigate();
  const novels = useNovelsStore((s) => s.novels);
  const load = useNovelsStore((s) => s.load);
  const novelId = useWorkspaceStore((s) => s.novelId);
  const setNovelId = useWorkspaceStore((s) => s.setNovelId);

  useEffect(() => {
    void load();
  }, [load]);

  const current = novels.find((n) => n.id === novelId) ?? null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "flex h-8 min-w-[190px] items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-2.5",
            "text-left text-[13px] transition-colors hover:bg-neutral-100",
            "dark:border-neutral-800 dark:bg-neutral-800/50 dark:hover:bg-neutral-800",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
          )}
        >
          {current ? (
            <span
              className="h-5 w-5 shrink-0 rounded"
              style={{ background: coverStyle(current.id) }}
              aria-hidden
            />
          ) : null}
          <span
            className={cn(
              "min-w-0 flex-1 truncate font-medium",
              !current && "text-neutral-400 dark:text-neutral-500",
            )}
          >
            {current ? current.name : "未选择作品"}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-xs text-neutral-500">
          切换作品
        </DropdownMenuLabel>
        {novels.length === 0 ? (
          <div className="px-2 py-3 text-xs text-neutral-500">
            还没有作品。去「开新书」或「素材库」创建一本。
          </div>
        ) : (
          novels.map((n) => (
            <DropdownMenuItem
              key={n.id}
              onSelect={() => setNovelId(n.id)}
              className="gap-2"
            >
              <span
                className="h-4 w-4 shrink-0 rounded-sm"
                style={{ background: coverStyle(n.id) }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate">{n.name}</span>
              <span className="shrink-0 text-[10px] text-neutral-500">
                {n.genre}
              </span>
            </DropdownMenuItem>
          ))
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/library?tab=works&new=1")}>
          <Plus className="h-3.5 w-3.5" />
          新建作品
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
