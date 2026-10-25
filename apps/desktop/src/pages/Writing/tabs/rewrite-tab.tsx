/**
 * 重写 Tab：选段重写。
 *
 * 与生成的差别：重写必须先有选区。没选区时按钮禁用并给出提示，
 * 而不是点了才报错（旧实现就是这样，交互体验差）。
 */

import { useEffect, useState } from "react";
import { Wand2, X } from "lucide-react";
import type { Chapter } from "@/lib/types";
import type { ChapterStreamApi } from "../use-chapter-stream";
import { Field, HintBar, StreamBox, ThinkingBox, panelInputClass } from "../ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  chapter: Chapter | null;
  stream: ChapterStreamApi;
  selection: { from: number; to: number; text: string } | null;
}

export default function RewriteTab({ chapter, stream, selection }: Props) {
  const [prompt, setPrompt] = useState("");
  const busy = stream.generating || stream.rewriting;

  // 选区变化时清掉上一次的指令（避免误用旧指令）
  useEffect(() => {
    setPrompt("");
  }, [selection?.from, selection?.to]);

  // 质检 Tab 点「重写这段」→ 带问题描述切过来，预填指令
  useEffect(() => {
    const onHint = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (typeof detail === "string" && detail.trim()) {
        setPrompt(detail.trim());
      }
    };
    window.addEventListener("book-soul:rewrite-hint", onHint);
    return () => window.removeEventListener("book-soul:rewrite-hint", onHint);
  }, []);

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
        <h4 className="text-[12.5px] font-semibold">重写选中的段落</h4>
        <p className="mt-0.5 mb-3.5 text-[11.5px] leading-relaxed text-neutral-400">
          在左边正文里选中一段文字，这里会显示选区并接收重写指令。
        </p>

        {selection ? (
          <div className="mb-3.5 rounded-lg border border-neutral-200 bg-neutral-50 p-2.5 dark:border-neutral-800 dark:bg-neutral-800/40">
            <div className="mb-1 flex items-center justify-between text-[11px]">
              <span className="text-neutral-500 dark:text-neutral-400">
                已选 {selection.text.length} 字
              </span>
              <span className="font-mono text-neutral-400">
                {selection.from}–{selection.to}
              </span>
            </div>
            <p className="max-h-[76px] overflow-hidden font-serif text-[12px] leading-relaxed text-neutral-500 dark:text-neutral-400">
              {selection.text.slice(0, 160)}
              {selection.text.length > 160 ? "…" : ""}
            </p>
          </div>
        ) : (
          <div className="mb-3.5">
            <HintBar tone="warn">还没有选中文字。在左边正文里拖选一段即可。</HintBar>
          </div>
        )}

        {stream.rewriting ? (
          <div className="mb-3.5 rounded-xl border border-violet-500/40 bg-gradient-to-b from-violet-500/10 to-transparent p-3">
            <div className="mb-2 flex items-center gap-2">
              <Wand2 className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-[12px] font-semibold text-violet-300">
                正在重写
              </span>
              <span className="ml-auto font-mono text-[10.5px] text-neutral-400">
                {String(Math.floor(stream.elapsed / 60)).padStart(2, "0")}:
                {String(stream.elapsed % 60).padStart(2, "0")}
              </span>
            </div>
            <ThinkingBox text={stream.thinkingText} />
            <StreamBox text={stream.streamText} tail={900} className="max-h-[150px]" />
          </div>
        ) : null}

        <Field label="重写要求" hint="例如：更紧凑 / 换对话风格 / 补心理活动">
          <textarea
            className={cn(panelInputClass, "min-h-[92px] resize-y leading-relaxed")}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={busy || !selection}
            placeholder="描述你想怎么改这段…"
          />
        </Field>

        {selection ? (
          <HintBar>重写会替换选区原文，原文保留在版本历史里，随时可回滚。</HintBar>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
        {stream.rewriting ? (
          <Button
            size="sm"
            variant="outline"
            className="w-full border-rose-500/50 text-rose-500 hover:text-rose-400"
            onClick={stream.stop}
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            停止重写
          </Button>
        ) : (
          <Button
            size="sm"
            className="w-full bg-violet-600 text-white hover:bg-violet-700"
            disabled={busy || !selection || !prompt.trim()}
            onClick={() => void stream.startRewrite(prompt, selection)}
          >
            <Wand2 className="mr-1.5 h-3.5 w-3.5" />
            重写选段
          </Button>
        )}
      </div>
    </div>
  );
}
