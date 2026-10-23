/**
 * 步骤 1 · 种子：选题材 + 挑关键词。
 *
 * 对应设计稿 s09。题材决定词库、题材常识与质检标准；
 * 词条会写进后面每一步的 prompt。
 */

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { wordbanksApi } from "@/api/wordbanks";
import { GENRE_DESC, GENRE_PRIORITY, type GenreDef } from "@/config/genres";
import { fetchRandomBatch } from "./wordbank";
import { cn } from "@/lib/utils";

interface Props {
  genre: GenreDef | null;
  onSelectGenre: (g: GenreDef | null) => void;
  keywords: Set<string>;
  onToggleKeyword: (kw: string) => void;
  onRemoveKeyword: (kw: string) => void;
  onClearKeywords: () => void;
}

export default function SeedStep({
  genre,
  onSelectGenre,
  keywords,
  onToggleKeyword,
  onRemoveKeyword,
  onClearKeywords,
}: Props) {
  const [categories, setCategories] = useState<string[]>([]);
  const [candidates, setCandidates] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  /** 拉首批候选（切题材时） */
  const fetchInitial = useCallback(async (g: GenreDef) => {
    setLoading(true);
    try {
      const meta = await wordbanksApi.getMeta(g.id);
      setCategories(meta.categories);
      const words = await fetchRandomBatch(g.id, meta.categories, 10, new Set());
      setCandidates(words);
    } catch (e: unknown) {
      toast.error("加载词库失败", {
        description: e instanceof Error ? e.message : String(e),
      });
      setCandidates([]);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (genre) {
      void fetchInitial(genre);
    } else {
      setCandidates([]);
      setCategories([]);
    }
  }, [genre, fetchInitial]);

  /** 换一批候选（已选的排除掉） */
  const refresh = useCallback(async () => {
    if (!genre) return;
    setLoading(true);
    try {
      const words = await fetchRandomBatch(
        genre.id,
        categories.length > 0 ? categories : [],
        10,
        keywords,
      );
      setCandidates(words);
    } catch (e: unknown) {
      toast.error("刷新词条失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setLoading(false);
    }
  }, [genre, categories, keywords]);

  return (
    <div>
      {/* 题材 */}
      <section className="mb-6">
        <div className="mb-2.5 flex items-baseline gap-2">
          <h3 className="text-[12.5px] font-semibold">题材</h3>
          <span className="text-[11.5px] text-neutral-400">
            决定词库、题材常识与质检标准
          </span>
        </div>
        <div className="grid grid-cols-4 gap-2.5">
          {GENRE_PRIORITY.map((g) => {
            const on = genre?.id === g.id;
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => onSelectGenre(g)}
                className={cn(
                  "flex items-center gap-2.5 rounded-xl border p-3 text-left transition-all",
                  on
                    ? "border-indigo-500 bg-indigo-500/10 shadow-[0_0_0_3px_rgba(99,102,241,.1)]"
                    : "border-neutral-200 bg-white hover:border-neutral-300 hover:bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700",
                )}
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-neutral-100 text-[18px] dark:bg-neutral-800">
                  {g.emoji}
                </span>
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium">{g.name}</span>
                  <span className="block truncate text-[10.5px] text-neutral-400">
                    {GENRE_DESC[g.id] ?? g.id}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      {/* 已选词条 */}
      {genre ? (
        <section className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="flex items-baseline gap-2 text-[12.5px] font-semibold">
              已选词条
              <span className="text-[11.5px] font-normal text-neutral-400">
                {keywords.size} 个 · 会写进每个 prompt
              </span>
            </h3>
            {keywords.size > 0 ? (
              <button
                type="button"
                onClick={onClearKeywords}
                className="text-[11.5px] text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
              >
                清空
              </button>
            ) : null}
          </div>
          {keywords.size === 0 ? (
            <p className="rounded-lg border border-dashed border-neutral-200 px-3 py-3 text-[11.5px] text-neutral-400 dark:border-neutral-800">
              还没选词条 —— 从下方候选池点选，或在底部输入框直接输入
            </p>
          ) : (
            <div className="flex min-h-[62px] flex-wrap gap-1.5 rounded-lg border border-indigo-500/40 bg-indigo-500/[0.06] p-3">
              {Array.from(keywords).map((kw) => (
                <span
                  key={kw}
                  className="inline-flex h-[27px] items-center gap-1.5 rounded-full border border-indigo-500/40 bg-indigo-500/10 pr-1.5 pl-3 text-[12px] text-indigo-600 dark:text-indigo-300"
                >
                  {kw}
                  <button
                    type="button"
                    onClick={() => onRemoveKeyword(kw)}
                    className="grid h-4 w-4 place-items-center rounded-full bg-black/5 text-[11px] text-indigo-500 transition-colors hover:bg-rose-500 hover:text-white dark:bg-white/10"
                    aria-label={`移除 ${kw}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {/* 候选池 */}
      {genre ? (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="flex items-baseline gap-2 text-[12.5px] font-semibold">
              候选词库
              <span className="text-[11.5px] font-normal text-neutral-400">
                点选加入上方
              </span>
            </h3>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading || categories.length === 0}
              className="inline-flex items-center gap-1 text-[11.5px] text-neutral-400 transition-colors hover:text-neutral-700 disabled:opacity-40 dark:hover:text-neutral-200"
            >
              <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
              刷新
            </button>
          </div>
          <div className="flex min-h-[62px] flex-wrap gap-1.5 rounded-lg border border-dashed border-neutral-200 p-3 dark:border-neutral-800">
            {loading && candidates.length === 0 ? (
              <span className="text-[11.5px] text-neutral-400">加载中…</span>
            ) : candidates.length === 0 ? (
              <span className="text-[11.5px] text-neutral-400 italic">
                暂无候选词条，点「刷新」换一批
              </span>
            ) : (
              candidates.map((kw) => {
                const on = keywords.has(kw);
                return (
                  <button
                    key={kw}
                    type="button"
                    onClick={() => onToggleKeyword(kw)}
                    className={cn(
                      "h-[27px] rounded-full border px-3 text-[12px] transition-colors",
                      on
                        ? "border-neutral-700 bg-neutral-700 text-white dark:border-neutral-300 dark:bg-neutral-300 dark:text-neutral-900"
                        : "border-neutral-200 text-neutral-600 hover:border-neutral-400 dark:border-neutral-800 dark:text-neutral-400 dark:hover:border-neutral-600",
                    )}
                  >
                    {kw}
                  </button>
                );
              })
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}
