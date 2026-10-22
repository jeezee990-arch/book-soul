/**
 * 种子步骤：选题材 + 选关键词。
 *
 * 这个视图自己管"候选池"（含加载 / 刷新 / 批量选择）的局部状态，
 * 已选关键词则由父组件持有（要跨步骤保留）。
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { wordbanksApi } from "@/api/wordbanks";
import { GENRE_PRIORITY, type GenreDef } from "@/config/genres";
import { Button } from "@/components/ui/button";
import { fetchRandomBatch } from "../wordbank";

/** 题材 + 关键词选择界面。 */
export default function SeedView({
  genre,
  onSelectGenre,
  keywords,
  onToggleKeyword,
  onRemoveKeyword,
  onRemoveKeywords,
  onGenerate,
  onBack,
}: {
  genre: GenreDef | null;
  onSelectGenre: (g: GenreDef | null) => void;
  keywords: Set<string>;
  onToggleKeyword: (kw: string) => void;
  onRemoveKeyword: (kw: string) => void;
  onRemoveKeywords: (kws: string[]) => void;
  onGenerate: () => void;
  onBack: () => void;
}) {
  // 题材的 wordbank categories（meta）
  const [categories, setCategories] = useState<string[]>([]);
  // 当前展示的候选池
  const [candidates, setCandidates] = useState<string[]>([]);
  // 加载态
  const [loading, setLoading] = useState(false);
  // 批量管理模式
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set());

  // 取 meta + 首批候选（按 genre 变化时拉）
  const fetchInitial = useCallback(async (g: GenreDef) => {
    setLoading(true);
    try {
      const meta = await wordbanksApi.getMeta(g.id);
      const cats = meta.categories;
      setCategories(cats);
      // 拉首批（每个分类拿 2 个，避免重复 + 已选）
      const words = await fetchRandomBatch(g.id, cats, 10, new Set());
      setCandidates(words);
    } catch (e) {
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

  // 刷新词条（拉新一批，已选保留，已选在池中保留可见）
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
    } catch (e) {
      toast.error("刷新词条失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setLoading(false);
    }
  }, [genre, categories, keywords]);

  // 批量删除
  const handleBulkDelete = useCallback(() => {
    if (bulkSelected.size === 0) return;
    onRemoveKeywords(Array.from(bulkSelected));
    setBulkSelected(new Set());
    setBulkMode(false);
    toast.success(`已删除 ${bulkSelected.size} 个词条`);
  }, [bulkSelected, onRemoveKeywords]);

  const toggleBulkOne = useCallback((kw: string) => {
    setBulkSelected((prev) => {
      const next = new Set(prev);
      if (next.has(kw)) next.delete(kw);
      else next.add(kw);
      return next;
    });
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">选题材 + 关键词</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            选好后点"生成 3 个剧情"会自动进入下一步
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 返回
        </Button>
      </header>

      {/* 题材选择 */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">题材</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {GENRE_PRIORITY.map((g) => (
            <button
              key={g.id}
              onClick={() => onSelectGenre(g)}
              className={`flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg border text-sm transition-all ${
                genre?.id === g.id
                  ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300"
                  : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700"
              }`}
            >
              <span>{g.emoji}</span>
              <span>{g.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 已选取词条 */}
      {genre && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
              已选取词条（{keywords.size}）
            </p>
            {keywords.size > 0 && (
              <button
                onClick={() => {
                  if (bulkMode && bulkSelected.size > 0) {
                    handleBulkDelete();
                  } else {
                    setBulkMode((v) => !v);
                    setBulkSelected(new Set());
                  }
                }}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  bulkMode && bulkSelected.size > 0
                    ? "bg-red-500 text-white hover:bg-red-600"
                    : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                }`}
              >
                {bulkMode && bulkSelected.size > 0
                  ? `删除选中 (${bulkSelected.size})`
                  : bulkMode
                    ? "退出批量"
                    : "批量管理"}
              </button>
            )}
          </div>

          {keywords.size === 0 ? (
            <p className="text-xs text-neutral-400 italic">还未选取词条；可以从下方候选池点选，或在底部输入框输入</p>
          ) : (
            <div className="flex flex-wrap gap-2 min-h-[2.5rem] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/40">
              {Array.from(keywords).map((kw) => {
                const isBulkSelected = bulkSelected.has(kw);
                const isFromCandidates = candidates.includes(kw);
                return (
                  <div
                    key={kw}
                    className={`group inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full text-sm border transition-all ${
                      isBulkSelected
                        ? "border-red-400 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
                        : isFromCandidates
                          ? "border-neutral-700 bg-neutral-700 text-white dark:border-neutral-300 dark:bg-neutral-300 dark:text-neutral-900"
                          : "border-indigo-300 bg-indigo-50 dark:border-indigo-700 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300"
                    }`}
                  >
                    {bulkMode && (
                      <button
                        type="button"
                        onClick={() => toggleBulkOne(kw)}
                        className="w-3.5 h-3.5 rounded-sm border flex items-center justify-center"
                        aria-label="选择"
                      >
                        {isBulkSelected && (
                          <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-red-600">
                            <path d="M2 6l3 3 5-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </button>
                    )}
                    <span>{kw}</span>
                    {!bulkMode && (
                      <button
                        type="button"
                        onClick={() => onRemoveKeyword(kw)}
                        className="w-5 h-5 rounded-full flex items-center justify-center opacity-60 hover:opacity-100 hover:bg-black/10 dark:hover:bg-white/10"
                        aria-label="删除"
                      >
                        <svg viewBox="0 0 12 12" className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 3l6 6m0-6l-6 6" strokeLinecap="round" />
                        </svg>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 候选池（可刷新） */}
      {genre && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
              关键词（候选池，点选加入已选）
            </p>
            <button
              onClick={refresh}
              disabled={loading || categories.length === 0}
              className="text-xs px-2.5 py-1 rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1"
              aria-label="刷新词条"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
              >
                <path d="M21 12a9 9 0 11-3-6.7M21 3v6h-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              刷新词条
            </button>
          </div>
          <div className="flex flex-wrap gap-2 min-h-[2.5rem] p-3 rounded-lg border border-dashed border-neutral-200 dark:border-neutral-800">
            {loading && candidates.length === 0 ? (
              <p className="text-xs text-neutral-400">加载中…</p>
            ) : candidates.length === 0 ? (
              <p className="text-xs text-neutral-400 italic">暂无候选词条；可点上方"刷新词条"换一批</p>
            ) : (
              candidates.map((kw) => {
                const isSelected = keywords.has(kw);
                return (
                  <button
                    key={kw}
                    onClick={() => onToggleKeyword(kw)}
                    className={`px-3 py-1.5 rounded-full text-sm border transition-all ${
                      isSelected
                        ? "border-neutral-700 bg-neutral-700 text-white dark:border-neutral-300 dark:bg-neutral-300 dark:text-neutral-900"
                        : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700"
                    }`}
                  >
                    {kw}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* 操作 */}
      <div className="flex items-center justify-end pt-4">
        <Button
          onClick={onGenerate}
          disabled={!genre || keywords.size === 0}
        >
          生成 3 个剧情 →
        </Button>
      </div>
    </div>
  );
}
