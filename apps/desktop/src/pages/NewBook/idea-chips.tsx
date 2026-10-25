/**
 * 想法词条（2026-10-25 新增）。
 *
 * 之前作者的想法只存在一个字符串里，输完只弹个 toast 就没了 ——
 * 想确认"我当时到底写了什么"、想改掉其中一条，都做不到。
 *
 * 现在每发一次想法就变成一个**可见的词条**：
 * - 显示在当前步骤内容区的下方
 * - 鼠标移上去才露出右边的删除按钮（平时藏起来，避免一排叉号晃眼）
 */

import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  /** 想法词条列表（按发送顺序） */
  ideas: string[];
  /** 删除某一条（按下标） */
  onRemove: (index: number) => void;
  /** 正在生成时禁用删除（避免中途改变上下文） */
  disabled?: boolean;
}

export default function IdeaChips({ ideas, onRemove, disabled = false }: Props) {
  if (ideas.length === 0) return null;

  return (
    <section className="mt-6">
      <div className="mb-2 flex items-baseline gap-2">
        <h3 className="text-[12.5px] font-semibold">我的想法</h3>
        <span className="text-[11.5px] font-normal text-neutral-400">
          {ideas.length} 条 · 会随下一次生成一起发给模型
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {ideas.map((idea, i) => (
          <span
            key={`${idea}-${i}`}
            /* group：让删除按钮只在鼠标移到这个词条上时才显形 */
            className={cn(
              "group inline-flex max-w-full items-center gap-1.5 rounded-full border",
              "border-amber-500/40 bg-amber-500/10 py-1 pl-3 pr-1.5 text-[12px]",
              "text-amber-700 dark:text-amber-300",
            )}
          >
            <span className="truncate" title={idea}>
              {idea}
            </span>
            <button
              type="button"
              onClick={() => onRemove(i)}
              disabled={disabled}
              aria-label={`删除想法：${idea}`}
              title="删除这条想法"
              className={cn(
                "grid h-4 w-4 shrink-0 place-items-center rounded-full text-[11px]",
                "text-amber-600 transition-all dark:text-amber-400",
                /* 平时完全透明，鼠标移上词条才淡入 */
                "opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
                "hover:bg-rose-500 hover:text-white",
                "disabled:pointer-events-none",
              )}
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </span>
        ))}
      </div>
    </section>
  );
}
