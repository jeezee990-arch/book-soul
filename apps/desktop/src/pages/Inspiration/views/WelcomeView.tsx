/** 欢迎页（流程起点）。 */

import { Button } from "@/components/ui/button";

/** 灵感园首页：引导用户开始创作。 */
export default function WelcomeView({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-8">
      <div className="space-y-6">
        <div className="w-20 h-20 mx-auto rounded-full bg-neutral-100 dark:bg-neutral-900 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-9 h-9 text-neutral-700 dark:text-neutral-300"
          >
            <path
              d="M12 6.5v13M5 4.5h6.5a2 2 0 012 2v13a2 2 0 00-2-2H5a2 2 0 01-2-2v-9a2 2 0 012-2zM19 4.5h-6.5a2 2 0 00-2 2v13a2 2 0 002-2H19a2 2 0 002-2v-9a2 2 0 00-2-2z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Book Soul，让创作更快捷
        </h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400 max-w-md mx-auto">
          从一句话种子到一部作品。AI 帮你跑通题材 → 词库 → 剧情 → 大纲 → 人物 → 章节的完整链路。
        </p>
      </div>
      <Button size="lg" onClick={onStart}>
        开始创作 →
      </Button>
    </div>
  );
}
