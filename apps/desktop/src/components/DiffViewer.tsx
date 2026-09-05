import { cn } from "@/lib/utils";

interface Props {
  /** unified diff 文本（来自后端 /versions/{id}/diff） */
  diff: string;
  className?: string;
  /** 可选：最大高度（px），超出滚动 */
  maxHeight?: number;
}

/** 纯文本 unified diff 渲染（Phase 4.6 v1，不依赖 react-diff-viewer-continued）。
 *
 * 颜色规则：
 * - ``+xxx``：绿色（新增）
 * - ``-xxx``：红色（删除）
 * - ``@@ -.. +.. @@``：紫色（hunk 头）
 * - ``--- / +++``：灰色（文件头）
 * - 其它：默认
 */
export default function DiffViewer({ diff, className, maxHeight = 480 }: Props) {
  if (!diff) {
    return (
      <p className="text-xs text-neutral-400 italic px-3 py-2">无差异</p>
    );
  }

  const lines = diff.split("\n");

  return (
    <pre
      className={cn(
        "rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50",
        "text-xs font-mono overflow-auto p-3 leading-relaxed",
        className,
      )}
      style={{ maxHeight }}
    >
      {lines.map((line, idx) => {
        let tone = "";
        if (line.startsWith("@@")) tone = "text-purple-600 dark:text-purple-400 bg-purple-50/40 dark:bg-purple-900/20";
        else if (line.startsWith("+++") || line.startsWith("---")) tone = "text-neutral-500";
        else if (line.startsWith("+")) tone = "text-emerald-700 dark:text-emerald-300 bg-emerald-50/40 dark:bg-emerald-900/20";
        else if (line.startsWith("-")) tone = "text-rose-700 dark:text-rose-300 bg-rose-50/40 dark:bg-rose-900/20";
        return (
          <div key={idx} className={cn("px-1 whitespace-pre-wrap", tone)}>
            {line || "\u00A0"}
          </div>
        );
      })}
    </pre>
  );
}
