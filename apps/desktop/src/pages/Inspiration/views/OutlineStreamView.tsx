/**
 * 大纲流式生成视图。
 *
 * 大纲是边生成边显示的纯文本流（不是 markdown 渲染，避免半成品 markdown
 * 闪烁），用 `<pre>` 保留换行。
 */

import { Button } from "@/components/ui/button";

/** 大纲生成中的界面。 */
export default function OutlineStreamView({
  text,
  onBack,
}: {
  text: string;
  onBack: () => void;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">正在生成大纲...</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            解析 + 自动建作品 + 调人物卡...
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 取消
        </Button>
      </header>
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 min-h-[400px]">
        <pre className="whitespace-pre-wrap text-sm leading-relaxed font-mono">
          {text || "…"}
        </pre>
      </div>
    </div>
  );
}
