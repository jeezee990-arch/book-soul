/**
 * 剧情版本列表视图（流式生成 + 选版）。
 *
 * 3 个版本并排展示；生成中的版本显示占位符且不可点选。
 */

import { Button } from "@/components/ui/button";
import type { GenreDef } from "@/config/genres";
import type { PlotVersion } from "../types";

/** 剧情生成 / 选版界面。 */
export default function PlotStreamView({
  genre,
  keywords,
  versions,
  streaming,
  isStreaming,
  chosenIdx,
  onChoose,
  onBack,
  userExtra,
}: {
  genre: GenreDef | null;
  keywords: Set<string>;
  versions: PlotVersion[];
  streaming: Record<number, string>;
  isStreaming: boolean;
  chosenIdx: number | null;
  onChoose: (idx: number) => void;
  onBack: () => void;
  userExtra: string;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">
            {isStreaming ? "正在生成剧情..." : "选择喜欢的剧情"}
          </h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            {genre?.name} · {keywords.size} 个关键词
            {userExtra && " · 含作者想法"}
          </p>
        </div>
        {!isStreaming && (
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← 返回
          </Button>
        )}
      </header>

      <div className="space-y-4">
        {Array.from({ length: 3 }, (_, i) => i + 1).map((idx) => {
          const v = versions.find((x) => x.index === idx);
          const text = v?.summary ?? streaming[idx] ?? "";
          const streamingHere = isStreaming && !v;
          const chosen = chosenIdx === idx;
          return (
            <button
              key={idx}
              onClick={() => text && !streamingHere && onChoose(idx)}
              disabled={streamingHere || !text}
              className={`w-full text-left rounded-xl border p-5 transition-all ${
                chosen
                  ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20"
                  : streamingHere
                    ? "border-neutral-300 dark:border-neutral-700 animate-pulse"
                    : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-600"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-neutral-400">
                  版本 {idx}
                </span>
                {streamingHere && (
                  <span className="text-[10px] text-neutral-400">生成中…</span>
                )}
                {chosen && (
                  <span className="text-xs text-indigo-600 dark:text-indigo-400">
                    ✓ 已选
                  </span>
                )}
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap min-h-[3em]">
                {text || (streamingHere ? "…" : "等待生成…")}
              </p>
            </button>
          );
        })}
      </div>

      {!isStreaming && chosenIdx === null && (
        <p className="text-xs text-neutral-400 text-center">点选一个剧情继续</p>
      )}
    </div>
  );
}
