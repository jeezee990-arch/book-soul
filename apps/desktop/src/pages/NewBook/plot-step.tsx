/**
 * 步骤 2 · 剧情：3 个版本并排生成 + 选一个。
 *
 * 对应设计稿 s10。三个版本各自独立流式渲染（互不阻塞），
 * 选中的那个作为下一步大纲与人物卡的基准。
 */

import { Check } from "lucide-react";
import type { GenreDef } from "@/config/genres";
import type { PlotVersion } from "./types";
import { cn } from "@/lib/utils";

interface Props {
  genre: GenreDef | null;
  keywords: Set<string>;
  versions: PlotVersion[];
  /** index → 流式中的文本 */
  streaming: Record<number, string>;
  isStreaming: boolean;
  chosenIdx: number | null;
  onChoose: (idx: number) => void;
}

export default function PlotStep({
  genre,
  keywords,
  versions,
  streaming,
  isStreaming,
  chosenIdx,
  onChoose,
}: Props) {
  return (
    <div>
      <div className="mb-5">
        <h2 className="text-[19px] font-semibold tracking-tight">
          挑一个你更想写的走向
        </h2>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-neutral-400">
          {genre?.name} · {keywords.size} 个关键词 ·{" "}
          {isStreaming
            ? "正在生成，稍等…"
            : "点卡片读全文，选中的那个会作为大纲和人物卡的基准"}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {[1, 2, 3].map((idx) => {
          const v = versions.find((x) => x.index === idx);
          const text = v?.summary ?? streaming[idx] ?? "";
          const streamingHere = isStreaming && !v;
          const chosen = chosenIdx === idx;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => text && !streamingHere && onChoose(idx)}
              disabled={streamingHere || !text}
              className={cn(
                "flex flex-col overflow-hidden rounded-xl border text-left transition-all",
                chosen
                  ? "border-indigo-500 shadow-[0_0_0_3px_rgba(99,102,241,.11)]"
                  : streamingHere
                    ? "border-neutral-300 animate-pulse dark:border-neutral-700"
                    : "border-neutral-200 hover:border-neutral-400 dark:border-neutral-800 dark:hover:border-neutral-600",
              )}
            >
              <div className="flex items-center gap-2 border-b border-neutral-200/70 px-3 py-2.5 dark:border-neutral-800/70">
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-mono text-[10.5px]",
                    chosen
                      ? "bg-indigo-500/15 text-indigo-500"
                      : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400",
                  )}
                >
                  走向 {String.fromCharCode(64 + idx)}
                </span>
                {streamingHere ? (
                  <span className="ml-auto inline-flex items-center gap-1 text-[10.5px] text-neutral-400">
                    <span className="inline-block h-2.5 w-[2px] bg-violet-500" />
                    生成中
                  </span>
                ) : null}
                {chosen ? (
                  <span className="ml-auto inline-flex items-center gap-1 text-[10.5px] font-medium text-indigo-500">
                    <Check className="h-3 w-3" />
                    已选中
                  </span>
                ) : null}
              </div>

              <div className="relative h-[212px] overflow-hidden p-3.5 font-serif text-[13px] leading-[1.85] text-neutral-600 dark:text-neutral-400">
                {text || (streamingHere ? "…" : "等待生成…")}
                {streamingHere ? (
                  <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
                ) : null}
              </div>

              <div className="border-t border-neutral-200/70 px-3 py-2.5 dark:border-neutral-800/70">
                <span
                  className={cn(
                    "text-[11.5px]",
                    chosen
                      ? "font-medium text-indigo-500"
                      : "text-neutral-400",
                  )}
                >
                  {streamingHere
                    ? "生成中…"
                    : chosen
                      ? "✓ 已选中"
                      : "点击选中"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {!isStreaming && chosenIdx === null ? (
        <p className="mt-4 text-center text-[11.5px] text-neutral-400">
          点选一个剧情继续
        </p>
      ) : null}
    </div>
  );
}
