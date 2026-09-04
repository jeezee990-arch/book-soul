import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { wordbanksApi } from "@/api/wordbanks";
import { ApiError } from "@/api";
import { GENRE_PRIORITY, type GenreDef } from "@/config/genres";
import type { WordbankMeta } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/** 每次刷新每个分类取的词数。 */
const WORDS_PER_CATEGORY = 10;

interface Props {
  /** 父组件传入的当前选中（受控）；null = 未选 */
  selected: GenreDef | null;
  /** 选中变化时通知父组件（传 null 表示取消） */
  onSelect: (g: GenreDef | null) => void;
}

/**
 * 题材选择 + 词库预览（Phase 3.1）。
 *
 * - 上方：4 个题材卡片（按 GENRE_PRIORITY 顺序）
 * - 选中后：拉元数据 + 5 类各 10 个随机词
 * - 刷新词：重新抽样（前端不存状态，每次重抽）
 * - 锁定按钮：占位，3.2 接入（在 KeywordBoard 里实现）
 */
export default function GenreSelect({ selected, onSelect }: Props) {
  const [meta, setMeta] = useState<WordbankMeta | null>(null);
  const [wordsByCat, setWordsByCat] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 用作刷新触发器（每次 +1，让 effect 重新跑）
  const [refreshTick, setRefreshTick] = useState(0);

  // 拉元数据
  useEffect(() => {
    if (!selected) {
      setMeta(null);
      setWordsByCat({});
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    wordbanksApi
      .getMeta(selected.id)
      .then((m) => {
        if (!cancelled) setMeta(m);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setError(msg);
          setMeta(null);
          toast.error("拉取材质词库失败", { description: msg });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  // 拉随机词（meta 或 refreshTick 变化时触发）
  useEffect(() => {
    if (!meta) {
      setWordsByCat({});
      return;
    }
    let cancelled = false;
    wordbanksApi
      .getRandom(meta.id, meta.categories, WORDS_PER_CATEGORY)
      .then((data) => {
        if (cancelled) return;
        // 后端单类返回 list、多类返回 dict；这里总是多类（meta.categories 全传）
        const map =
          Array.isArray(data)
            ? { [meta.categories[0] ?? ""]: data }
            : (data as Record<string, string[]>);
        setWordsByCat(map);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setWordsByCat({});
          toast.error("抽取灵感词失败", { description: msg });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [meta, refreshTick]);

  const handleSelect = useCallback(
    (g: GenreDef) => {
      onSelect(selected?.id === g.id ? null : g);
      setRefreshTick(0);
    },
    [selected, onSelect],
  );

  const handleRefresh = useCallback(() => {
    setRefreshTick((t) => t + 1);
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">第一步：选择题材</CardTitle>
        <CardDescription>
          题材决定词库范围与提示词风格。选定后下方展示可用的灵感词分类与示例。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* 题材卡片网格 */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {GENRE_PRIORITY.map((g) => {
            const isSelected = selected?.id === g.id;
            return (
              <button
                key={g.id}
                type="button"
                onClick={() => handleSelect(g)}
                className={[
                  "rounded-lg border p-4 text-left transition-colors",
                  "hover:bg-neutral-50 dark:hover:bg-neutral-900",
                  "focus:outline-none focus:ring-2 focus:ring-neutral-400",
                  isSelected
                    ? "border-neutral-900 dark:border-neutral-100 ring-1 ring-neutral-900 dark:ring-neutral-100"
                    : "border-neutral-200 dark:border-neutral-800",
                ].join(" ")}
                aria-pressed={isSelected}
              >
                <div className="text-3xl leading-none">{g.emoji}</div>
                <div className="mt-2 text-sm font-medium">{g.name}</div>
                <div className="mt-1 text-[10px] uppercase tracking-wider text-neutral-400">
                  {g.tier}
                </div>
              </button>
            );
          })}
        </div>

        {/* 选中后展示词库预览 */}
        {selected && (
          <div className="space-y-3 border-t border-neutral-200 dark:border-neutral-800 pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium">
                  {selected.emoji} {selected.name}
                </span>
                <span className="text-xs text-neutral-500">· 词库预览</span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={loading}
                >
                  刷新词
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled
                  title="3.2 接入"
                >
                  锁定
                </Button>
              </div>
            </div>

            {loading && (
              <p className="text-xs text-neutral-400">加载元数据中…</p>
            )}

            {error && !loading && (
              <p className="text-xs text-destructive">加载失败：{error}</p>
            )}

            {meta && !loading && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  {meta.categories.map((c) => (
                    <span
                      key={c}
                      className="inline-flex items-center rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 px-2 py-0.5 text-[11px] font-mono text-neutral-600 dark:text-neutral-400"
                    >
                      {c} · {meta.counts[c] ?? 0}
                    </span>
                  ))}
                </div>
                <div className="space-y-2">
                  {meta.categories.map((c) => {
                    const words = wordsByCat[c] ?? [];
                    return (
                      <div
                        key={c}
                        className="grid grid-cols-[80px_1fr] items-start gap-3"
                      >
                        <div className="text-xs text-neutral-500 pt-0.5 font-mono">
                          {c}
                        </div>
                        <div className="text-sm leading-relaxed">
                          {words.length > 0
                            ? words.join("、")
                            : <span className="text-neutral-400">（暂无）</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
