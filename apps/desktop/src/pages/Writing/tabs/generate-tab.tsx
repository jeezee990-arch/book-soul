/**
 * 生成 Tab：生成本章正文。
 *
 * 沿用旧创作页的全部流式逻辑（迁移到 useChapterStream），
 * 这里只负责收集参数 + 展示流式状态。
 */

import { useState } from "react";
import { Sparkles, X } from "lucide-react";
import type { Chapter, Novel } from "@/lib/types";
import type { ChapterStreamApi } from "../use-chapter-stream";
import type { PanelTab } from "../types";
import { Field, HintBar, StreamBox, ThinkingBox, panelInputClass } from "../ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * 目标字数范围（硬上限来自 config/llm.yaml 的 chapter_limits）。
 *
 * 2026-10-29 需求3：原来是 1k/2k/4k/6k/8k 五个固定档位，
 * 想取 3500 字只能选 4000 —— 改成**滑动条**，1000~8000 连续可调、步进 100。
 */
const WORD_MIN = 1000;
const WORD_MAX = 8000;
const WORD_STEP = 100;

interface Props {
  novel: Novel | null;
  chapter: Chapter | null;
  stream: ChapterStreamApi;
  onSwitchTab: (tab: PanelTab) => void;
}

export default function GenerateTab({ novel, chapter, stream, onSwitchTab }: Props) {
  const [targetNum, setTargetNum] = useState(4000);
  const [prompt, setPrompt] = useState("");

  const busy = stream.generating || stream.rewriting;

  if (!chapter) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        先在左边选一个章节
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="min-h-0 flex-1 px-3.5 py-3.5">
        <h4 className="text-[12.5px] font-semibold">生成本章正文</h4>
        <p className="mt-0.5 mb-3.5 text-[11.5px] leading-relaxed text-neutral-400">
          人物卡与上下文自动注入，你只需补充本章要点。
        </p>

        {stream.generating ? (
          <div className="mb-3.5 rounded-xl border border-violet-500/40 bg-gradient-to-b from-violet-500/10 to-transparent p-3">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-[12px] font-semibold text-violet-300">
                正在生成正文
              </span>
              <span className="ml-auto font-mono text-[10.5px] text-neutral-400">
                {String(Math.floor(stream.elapsed / 60)).padStart(2, "0")}:
                {String(stream.elapsed % 60).padStart(2, "0")}
              </span>
            </div>
            <ThinkingBox text={stream.thinkingText} />
            <StreamBox
              text={stream.streamText}
              tail={1200}
              className="max-h-[190px]"
            />
            <div className="mt-2.5 border-t border-violet-500/20 pt-2.5">
              <span className="font-mono text-[18px] font-semibold text-violet-300">
                {stream.streamText.length.toLocaleString()}
              </span>
              <span className="ml-1.5 text-[11px] text-neutral-400">
                / {targetNum.toLocaleString()} 字
              </span>
            </div>
          </div>
        ) : null}

        <Field label="目标字数" hint={`${WORD_MIN}~${WORD_MAX} 字`}>
          <div className="flex items-center gap-2.5">
            <input
              type="range"
              min={WORD_MIN}
              max={WORD_MAX}
              step={WORD_STEP}
              value={targetNum}
              disabled={busy}
              aria-label="目标字数"
              onChange={(e) => setTargetNum(Number(e.target.value))}
              className="h-1.5 w-full min-w-0 cursor-pointer rounded-full bg-neutral-200 accent-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-neutral-700"
            />
            <span className="w-[62px] shrink-0 text-right font-mono text-[12px] font-medium text-violet-500">
              {targetNum.toLocaleString()}
            </span>
          </div>
        </Field>

        <Field label="本章要点" hint="选填">
          <textarea
            className={cn(panelInputClass, "min-h-[104px] resize-y leading-relaxed")}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={busy}
            placeholder="例：林川发现断剑震动，循声走到剑冢深处，遇见守冢老人。结尾留一个悬念。"
          />
        </Field>

        {novel ? (
          <HintBar tone="ai">
            将带入本书人物卡（仅本章出场者）+ 最近 3 章摘要 + 上一章尾部
          </HintBar>
        ) : null}
      </div>

      {/* 底部操作区 */}
      <div className="shrink-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
        {stream.generating ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="flex-1 border-rose-500/50 text-rose-500 hover:text-rose-400"
              onClick={stream.stop}
            >
              <X className="mr-1.5 h-3.5 w-3.5" />
              停止生成
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="flex-1"
              onClick={() => onSwitchTab("versions")}
            >
              查看版本
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            className="w-full bg-violet-600 text-white hover:bg-violet-700"
            disabled={busy}
            onClick={() => void stream.startGenerate(prompt, targetNum)}
          >
            <Sparkles className="mr-1.5 h-3.5 w-3.5" />
            生成正文
          </Button>
        )}
      </div>
    </div>
  );
}
