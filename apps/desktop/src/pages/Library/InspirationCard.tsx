/**
 * 素材库单条卡片（2026-10-29）。
 *
 * 三种状态：
 * - 普通：点卡片打开详情
 * - 管理模式：左侧多一个勾选框，点卡片切换勾选
 * - 拖拽中：被拖项半透明 + 落点显示插入指示线
 *
 * 拖拽用 **长按**（≥300ms）或 **按住移动超阈值** 触发，
 * 普通点击仍然打开详情（不冲突）。
 */

import { ExternalLink, Pin, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Inspiration } from "@/lib/types";
import { deriveInspirationTitle } from "./inspiration-manage";

const TYPE_LABEL: Record<string, string> = {
  keyword: "关键词",
  plot: "剧情",
  snippet: "片段",
  image: "画面",
  note: "备注",
};

const TYPE_TONE: Record<string, string> = {
  keyword: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200",
  plot: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200",
  snippet: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200",
  image: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
  note: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200",
};

/** 内容的摘要（卡片正文用，比派生标题长一点）。 */
function summarizeContent(ins: Inspiration): string {
  const c = ins.content ?? {};
  switch (ins.type) {
    case "keyword":
      return (c.words as string[] | undefined)?.join(" · ") ?? "（空）";
    case "plot":
      return (c.summary as string | undefined)?.slice(0, 100) ?? "（空）";
    case "snippet":
      return (c.text as string | undefined)?.slice(0, 100) ?? "（空）";
    case "image":
      return (c.description as string | undefined)?.slice(0, 100) ?? "（空）";
    case "note":
      return (c.text as string | undefined)?.slice(0, 100) ?? "（空）";
    default:
      return JSON.stringify(c).slice(0, 100);
  }
}

interface Props {
  ins: Inspiration;
  /** 关联作品名（没有关联作品时为 null）。 */
  novelName: string | null;
  /** 是否处于管理（批量选择）模式。 */
  manageMode: boolean;
  /** 管理模式下是否已勾选。 */
  selected: boolean;
  /** 该条目是否正被拖动。 */
  dragging: boolean;
  /** 插入指示线画在条目的上边（true）或下边（false）。 */
  indicatorBefore: boolean;
  /** 插入指示线是否可见。 */
  indicatorVisible: boolean;
  /** 打开详情。 */
  onOpen: (ins: Inspiration) => void;
  /** 删除。 */
  onDelete: (ins: Inspiration) => void;
  /** 切换勾选。 */
  onToggleSelect: (ins: Inspiration) => void;
  /** 按下卡片（长按拖动起点）。 */
  onPointerDown: (e: React.PointerEvent, ins: Inspiration) => void;
  /** 右键（打开上下文菜单）。 */
  onContextMenu?: (e: React.MouseEvent, ins: Inspiration) => void;
}

/**
 * 单条素材卡片。
 *
 * @param props - 组件属性
 */
export default function InspirationCard({
  ins,
  novelName,
  manageMode,
  selected,
  dragging,
  indicatorBefore,
  indicatorVisible,
  onOpen,
  onDelete,
  onToggleSelect,
  onPointerDown,
  onContextMenu,
}: Props) {
  const title = deriveInspirationTitle(ins);

  return (
    <Card
      data-inspiration-id={ins.id}
      onPointerDown={(e) => onPointerDown(e, ins)}
      onContextMenu={(e) => onContextMenu?.(e, ins)}
      onClick={() => {
        if (manageMode) onToggleSelect(ins);
        else onOpen(ins);
      }}
      className={cn(
        "relative cursor-pointer transition-colors hover:border-neutral-300 dark:hover:border-neutral-700",
        // 拖动中的条目不接收指针事件 —— 这样 elementFromPoint 能命中下面的条目
        dragging && "pointer-events-none opacity-40",
        selected && "border-indigo-400 dark:border-indigo-500/60",
      )}
    >
      {/* 置顶色条（克制，不用警告色） */}
      {ins.pinned ? (
        <span className="absolute inset-y-0 left-0 w-[2px] rounded-l-lg bg-amber-400/70" />
      ) : null}

      {/* 落点插入指示线 */}
      {indicatorVisible ? (
        <span
          className={cn(
            "absolute left-2 right-2 h-0.5 rounded-full bg-indigo-500",
            indicatorBefore ? "-top-px" : "-bottom-px",
          )}
        />
      ) : null}

      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {manageMode ? (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(ins)}
              onClick={(e) => e.stopPropagation()}
              aria-label={`选择 ${title}`}
              className="h-3.5 w-3.5 shrink-0 accent-indigo-600"
            />
          ) : null}

          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px]",
              TYPE_TONE[ins.type] ?? TYPE_TONE.note,
            )}
          >
            {TYPE_LABEL[ins.type] ?? ins.type}
          </span>

          <CardTitle className="truncate text-sm" title={title}>
            {title}
          </CardTitle>

          {ins.pinned ? (
            <Pin
              className="h-3 w-3 shrink-0 text-amber-500/80"
              aria-label="已置顶"
            />
          ) : null}

          {novelName ? (
            <span className="flex shrink-0 items-center gap-1 text-[10px] text-neutral-500">
              <ExternalLink className="h-3 w-3" />
              {novelName}
            </span>
          ) : null}

          <span className="ml-auto shrink-0 text-[10px] text-neutral-400">
            {new Date(ins.created_at).toLocaleString("zh-CN", { hour12: false })}
          </span>
        </div>
      </CardHeader>

      <CardContent>
        <p className="line-clamp-2 text-sm text-neutral-700 dark:text-neutral-300">
          {summarizeContent(ins)}
        </p>
        {ins.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {ins.tags.map((t: string) => (
              <span
                key={t}
                className="rounded border border-neutral-200 px-1.5 py-0.5 text-[10px] text-neutral-500 dark:border-neutral-800"
              >
                #{t}
              </span>
            ))}
          </div>
        )}
        <div className="mt-3 flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              onOpen(ins);
            }}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <ExternalLink className="mr-1.5 h-3 w-3" />
            查看详情
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(ins);
            }}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <Trash2 className="mr-1.5 h-3 w-3" />
            删除
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
