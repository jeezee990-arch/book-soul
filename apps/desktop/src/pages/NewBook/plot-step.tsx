/**
 * 步骤 2 · 剧情：3 个版本并排生成 + 选一个。
 *
 * 对应设计稿 s10。三个版本各自独立流式渲染（互不阻塞），
 * 选中的那个作为下一步大纲与人物卡的基准。
 *
 * 两个关键修复（2026-10-24，用户实测反馈）：
 *
 * 1. **卡片必须能滚动**。之前内容区是固定高 `h-[212px]` + `overflow-hidden` ——
 *    文字流到 212px 就被裁掉，后面的字渲染了但**看不见**，
 *    用户看到的就是"生成到一半卡住了"。改成 `max-h` + `overflow-y-auto`。
 *
 * 2. **自动跟随最新内容**。流式时把滚动条压到底部，
 *    用户不用手动拖就能看到"正在写的字"（原来只能盯着开头那一段）。
 */

import { useEffect, useRef } from "react";
import { Check } from "lucide-react";
import type { GenreDef } from "@/config/genres";
import type { GenStats, PlotVersion } from "./types";
import { isNearBottom, scrollToBottom } from "@/lib/auto-scroll";
import { cn } from "@/lib/utils";

interface Props {
  genre: GenreDef | null;
  keywords: Set<string>;
  versions: PlotVersion[];
  /** index → 流式中的文本 */
  streaming: Record<number, string>;
  /** index → 模型思考中的文本（<think> 块，用来显示"模型思考中…"） */
  thinking: Record<number, string>;
  isStreaming: boolean;
  /** 本次生成已耗时（秒） */
  elapsedSec: number;
  /** 生成完成后的统计（模型 + 总耗时 + 首字延迟） */
  stats: GenStats | null;
  chosenIdx: number | null;
  onChoose: (idx: number) => void;
}

const VERSION_IDX = [1, 2, 3];

export default function PlotStep({
  genre,
  keywords,
  versions,
  streaming,
  thinking,
  isStreaming,
  elapsedSec,
  stats,
  chosenIdx,
  onChoose,
}: Props) {
  /** 每个卡片内容区的 DOM 引用（用于自动滚到底） */
  const bodyRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // 流式内容变化 → 把还在底部的内容区压到底部
  //
  // 只在"用户本来就在底部附近"时才自动滚：否则用户想回头看前面写的字，
  // 会被强行拽回底部（很烦）。
  useEffect(() => {
    for (const idx of VERSION_IDX) {
      const el = bodyRefs.current[idx];
      if (!el) continue;
      if (isNearBottom(el)) scrollToBottom(el);
    }
  }, [streaming]);

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-[19px] font-semibold tracking-tight">
          挑一个你更想写的走向
        </h2>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-neutral-400">
          {genre?.name} · {keywords.size} 个关键词 ·{" "}
          {isStreaming ? (
            `正在生成（${elapsedSec}s）…`
          ) : stats ? (
            <span className="text-neutral-500 dark:text-neutral-300">
              {stats.model || "当前模型"} · 用时 {stats.elapsedSec}s
              {stats.firstDeltaSec != null ? ` · 首字 ${stats.firstDeltaSec}s` : ""}
            </span>
          ) : (
            "点卡片读全文，选中的那个会作为大纲和人物卡的基准"
          )}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {VERSION_IDX.map((idx) => {
          const v = versions.find((x) => x.index === idx);
          const text = v?.summary ?? streaming[idx] ?? "";
          const thinkingText = thinking[idx] ?? "";
          const streamingHere = isStreaming && !v;
          const thinkingNow = streamingHere && !text && thinkingText.length > 0;
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
                    {thinkingNow ? "模型思考中…" : "生成中"}
                  </span>
                ) : null}
                {chosen ? (
                  <span className="ml-auto inline-flex items-center gap-1 text-[10.5px] font-medium text-indigo-500">
                    <Check className="h-3 w-3" />
                    已选中
                  </span>
                ) : null}
              </div>

              {/*
                内容区：固定最大高 + **可滚动**（原来 overflow-hidden 会把
                超出部分裁掉 → 流式看起来"卡住"）。
              */}
              <div
                ref={(el) => {
                  bodyRefs.current[idx] = el;
                }}
                className="relative max-h-[212px] min-h-[120px] overflow-y-auto p-3.5 font-serif text-[13px] leading-[1.85] text-neutral-600 dark:text-neutral-400"
              >
                {thinkingNow ? (
                  <span className="text-neutral-400">
                    {thinkingText.slice(-40).trim()}
                    <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
                  </span>
                ) : (
                  <>
                    {text || (streamingHere ? "…" : "等待生成…")}
                    {streamingHere ? (
                      <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
                    ) : null}
                  </>
                )}
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
                    ? `生成中… ${elapsedSec}s`
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
