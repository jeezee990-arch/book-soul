/** 完成页：作品已就绪，引导进入章节创作。 */

import { Button } from "@/components/ui/button";
import type { NovelState } from "../types";

/** 生成结束后的确认界面。 */
export default function DoneView({
  novelMeta,
  charCount,
  onCreateChapters,
  onRestart,
}: {
  novelMeta: NovelState;
  charCount: number;
  onCreateChapters: () => void;
  onRestart: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center space-y-6">
      <div className="w-16 h-16 mx-auto rounded-full bg-green-100 dark:bg-green-950/30 flex items-center justify-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="w-8 h-8 text-green-600 dark:text-green-400"
        >
          <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">作品《{novelMeta.name}》已就绪</h2>
        <p className="text-sm text-neutral-500">
          1 个大纲 · {charCount} 个人物卡
        </p>
      </div>
      <div className="flex gap-3">
        <Button onClick={onCreateChapters}>去创作章节 →</Button>
        <Button variant="outline" onClick={onRestart}>
          再写一本
        </Button>
      </div>
    </div>
  );
}
