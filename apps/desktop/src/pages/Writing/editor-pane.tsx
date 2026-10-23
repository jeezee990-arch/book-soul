/**
 * 纸感编辑区（写作页中栏）。
 *
 * 设计要点：编辑区**固定浅色纸面**（不随主题切换）——
 * 深色外壳 + 浅色纸面是长篇写作最舒服的组合（Ulysses / 思源笔记的思路）。
 * 浅色模式下整页仍是浅色，不会有割裂感。
 */

import { forwardRef } from "react";
import { Check, Sparkles, Wand2 } from "lucide-react";
import NovelEditor, {
  type NovelEditorHandle,
  type NovelEditorSelection,
} from "@/components/NovelEditor";
import type { Chapter } from "@/lib/types";
import type { PanelTab } from "./types";
import { cn } from "@/lib/utils";

interface Props {
  chapter: Chapter | null;
  /** 编辑器内容（HTML） */
  content: string;
  /** 内容变化回调（HTML） */
  onContentChange: (html: string) => void;
  /** 选区变化回调 */
  onSelection: (sel: NovelEditorSelection | null) => void;
  /** 是否可编辑（生成中锁定） */
  editable: boolean;
  /** 加载中 */
  loading: boolean;
  /** 已保存的版本 id（显示"已保存 vN"） */
  savedVersionId: number | null;
  /** 点击顶部按钮切到对应右栏 Tab */
  onOpenTab: (tab: PanelTab) => void;
  /** 是否有选区（决定"重写"按钮是否高亮） */
  hasSelection: boolean;
}

const EditorPane = forwardRef<NovelEditorHandle, Props>(function EditorPane(
  {
    chapter,
    content,
    onContentChange,
    onSelection,
    editable,
    loading,
    savedVersionId,
    onOpenTab,
    hasSelection,
  },
  ref,
) {
  return (
    <section className="flex min-w-0 flex-1 flex-col bg-neutral-50 dark:bg-neutral-950">
      {/* 章节头 */}
      <header className="flex h-[46px] shrink-0 items-center gap-2.5 border-b border-neutral-200/70 px-4 dark:border-neutral-800/70">
        <h2 className="truncate text-[13.5px] font-semibold">
          {chapter
            ? `第 ${chapter.chapter_number} 章${chapter.title ? ` · ${chapter.title}` : ""}`
            : "未选择章节"}
        </h2>
        {chapter?.outline ? (
          <span className="hidden max-w-[280px] truncate text-[11px] text-neutral-400 md:inline">
            {chapter.outline}
          </span>
        ) : null}

        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onOpenTab("generate")}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-[11.5px] transition-colors",
              "border-violet-500/40 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20",
            )}
          >
            <Sparkles className="h-3.5 w-3.5" />
            生成
          </button>
          <button
            type="button"
            onClick={() => onOpenTab("rewrite")}
            disabled={!hasSelection}
            title={hasSelection ? "重写选中的段落" : "先在正文里选中一段"}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-[11.5px] transition-colors",
              hasSelection
                ? "border-violet-500/40 bg-violet-500/10 text-violet-300 hover:bg-violet-500/20"
                : "cursor-not-allowed border-neutral-200 text-neutral-400 dark:border-neutral-800",
            )}
          >
            <Wand2 className="h-3.5 w-3.5" />
            重写
          </button>
          <button
            type="button"
            onClick={() => onOpenTab("quality")}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-[11.5px] transition-colors",
              "border-indigo-500/40 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20",
            )}
          >
            <Check className="h-3.5 w-3.5" />
            质检
          </button>
        </div>
      </header>

      {/* 纸面 */}
      <div className="min-h-0 flex-1 overflow-y-auto py-6 pb-16">
        {loading ? (
          <div className="mx-auto w-[760px] space-y-3 rounded-lg bg-[#faf8f3] p-10">
            {[92, 78, 85, 60].map((w, i) => (
              <div
                key={i}
                className="h-4 animate-pulse rounded bg-neutral-200"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        ) : (
          <div className="novel-paper mx-auto w-[760px] max-w-[92%] rounded-lg px-14 py-10 pb-14">
            {chapter ? (
              <NovelEditor
                ref={ref}
                content={content}
                onChange={onContentChange}
                onSelection={(sel) => onSelection(sel)}
                editable={editable}
                placeholder="开始写这一章……"
              />
            ) : (
              <p className="text-center text-[13px] text-neutral-400">
                左边选一个章节开始写
              </p>
            )}
          </div>
        )}
      </div>

      {/* 状态栏 */}
      <footer className="flex h-8 shrink-0 items-center gap-3.5 border-t border-neutral-200/70 px-4 text-[11px] text-neutral-400 dark:border-neutral-800/70">
        {savedVersionId !== null ? (
          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <Check className="h-3 w-3" />
            已保存 v{savedVersionId}
          </span>
        ) : null}
        <span className="font-mono">
          {chapter ? chapter.word_count.toLocaleString() : 0} 字
        </span>
        <span className="hidden md:inline">
          上下文：人物卡 · 最近 3 章摘要 · 上一章尾部
        </span>
        <span className="ml-auto">UTF-8</span>
      </footer>
    </section>
  );
});

export default EditorPane;
