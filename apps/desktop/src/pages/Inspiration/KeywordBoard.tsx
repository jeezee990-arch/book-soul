import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { wordbanksApi } from "@/api/wordbanks";
import { inspirationsApi } from "@/api/inspirations";
import { ApiError } from "@/api";
import type { GenreDef } from "@/config/genres";
import type { WordbankMeta } from "@/lib/types";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import WordSection from "./WordSection";

/** 每个分类的抽样数（与 GenreSelect 保持一致）。 */
const WORDS_PER_CATEGORY = 10;

interface Props {
  /** 父组件传入的已选题材（GenreSelect 选中后）。 */
  genre: GenreDef;
  /** 受控：当前选中的关键词集合（父组件持有 state）。 */
  selected: Set<string>;
  /** 受控变化回调：把"下一个 Set"传给父，父用 setState(prev => next) 更新。 */
  onSelectionChange: (next: Set<string>) => void;
}

/**
 * 灵感词交互面板（Phase 3.2 + 3.3）。
 *
 * - 词条可点选（多选）；selected 由父组件持有，供 PlotGenerator 消费
 * - 工具栏：刷新 / 全选（当前分类）/ 反选（当前分类）/ 清除 / 锁定选中 / 解除全部锁定 / 保存草稿
 * - 锁定：刷新时锁定词位置保留，其他词重抽
 * - 手动添加：输入框 + Enter 或 + 按钮
 * - 提示词框：始终显示当前选中词 + 统计
 */
export default function KeywordBoard({
  genre,
  selected,
  onSelectionChange,
}: Props) {
  const [meta, setMeta] = useState<WordbankMeta | null>(null);
  const [wordsByCat, setWordsByCat] = useState<Record<string, string[]>>({});
  const [activeCat, setActiveCat] = useState<string | null>(null);
  const [locked, setLocked] = useState<Set<string>>(new Set());
  const [manualWords, setManualWords] = useState<string[]>([]);
  const [manualInput, setManualInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  // 拉元数据
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setMeta(null);
    setWordsByCat({});
    setActiveCat(null);
    wordbanksApi
      .getMeta(genre.id)
      .then((m) => {
        if (!cancelled) {
          setMeta(m);
          setActiveCat(m.categories[0] ?? null);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) toast.error("拉取材质词库失败", { description: msg });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [genre.id]);

  // 拉随机词：meta 或 refreshTick 变化时重抽；锁定词位置保留
  // （locked 不进依赖，避免 选中→锁→刷新 形成死循环）
  useEffect(() => {
    if (!meta) return;
    let cancelled = false;
    const lockedSnapshot = new Set(locked);
    wordbanksApi
      .getRandom(meta.id, meta.categories, WORDS_PER_CATEGORY)
      .then((data) => {
        if (cancelled) return;
        const map = Array.isArray(data)
          ? { [meta.categories[0] ?? ""]: data }
          : (data as Record<string, string[]>);
        setWordsByCat((prev) => {
          const next: Record<string, string[]> = {};
          for (const cat of meta.categories) {
            const fresh = map[cat] ?? [];
            const keep = (prev[cat] ?? []).filter((w) => lockedSnapshot.has(w));
            const seen = new Set(keep);
            const merged: string[] = [...keep];
            for (const w of fresh) {
              if (!seen.has(w)) {
                seen.add(w);
                merged.push(w);
              }
            }
            next[cat] = merged;
          }
          return next;
        });
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) toast.error("抽取灵感词失败", { description: msg });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta, refreshTick]);

  // ===== handlers =====
  const handleRefresh = useCallback(() => {
    setRefreshTick((t) => t + 1);
  }, []);

  const handleSelectAll = useCallback(() => {
    if (!activeCat) return;
    const words = wordsByCat[activeCat] ?? [];
    onSelectionChange(new Set([...selected, ...words]));
  }, [activeCat, wordsByCat, selected, onSelectionChange]);

  const handleInvert = useCallback(() => {
    if (!activeCat) return;
    const words = wordsByCat[activeCat] ?? [];
    const next = new Set(selected);
    for (const w of words) {
      if (next.has(w)) next.delete(w);
      else next.add(w);
    }
    onSelectionChange(next);
  }, [activeCat, wordsByCat, selected, onSelectionChange]);

  const handleClear = useCallback(() => {
    onSelectionChange(new Set());
  }, [onSelectionChange]);

  const handleLockSelected = useCallback(() => {
    if (selected.size === 0) {
      toast.info("请先选中要锁定的词");
      return;
    }
    setLocked((prev) => new Set([...prev, ...selected]));
    toast.success(`已锁定 ${selected.size} 个词`);
  }, [selected]);

  const handleUnlockAll = useCallback(() => {
    if (locked.size === 0) return;
    setLocked(new Set());
  }, [locked.size]);

  const handleToggleWord = useCallback(
    (w: string) => {
      const next = new Set(selected);
      if (next.has(w)) next.delete(w);
      else next.add(w);
      onSelectionChange(next);
    },
    [selected, onSelectionChange],
  );

  const handleManualAdd = useCallback(() => {
    const w = manualInput.trim();
    if (!w) return;
    setManualWords((prev) => (prev.includes(w) ? prev : [...prev, w]));
    onSelectionChange(new Set([...selected, w]));
    setManualInput("");
  }, [manualInput, selected, onSelectionChange]);

  const handleSaveDraft = useCallback(async () => {
    if (selected.size === 0) {
      toast.info("请先选择关键词");
      return;
    }
    setSaving(true);
    try {
      await inspirationsApi.create({
        novel_id: null,
        type: "keyword",
        content: { words: Array.from(selected) },
        source: `KeywordBoard:${genre.id}`,
        tags: [genre.id, "draft"],
      });
      toast.success(`已保存 ${selected.size} 个关键词到草稿库`);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("保存失败", { description: msg });
    } finally {
      setSaving(false);
    }
  }, [selected, genre.id]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          第二步：灵感词（{genre.name}）
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleRefresh}
            disabled={loading || !meta}
          >
            刷新词
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleSelectAll}
            disabled={!activeCat}
          >
            全选
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleInvert}
            disabled={!activeCat}
          >
            反选
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleClear}
            disabled={selected.size === 0}
          >
            清除
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleLockSelected}
            disabled={selected.size === 0}
          >
            锁定选中（{selected.size}）
          </Button>
          {locked.size > 0 && (
            <Button size="sm" variant="ghost" onClick={handleUnlockAll}>
              解除全部锁定（{locked.size}）
            </Button>
          )}
          <div className="ml-auto">
            <Button
              size="sm"
              onClick={handleSaveDraft}
              disabled={saving || selected.size === 0}
            >
              {saving ? "保存中..." : "💾 保存草稿"}
            </Button>
          </div>
        </div>

        {meta && (
          <WordSection
            categories={meta.categories}
            activeCat={activeCat}
            onChangeActive={setActiveCat}
            wordsByCat={wordsByCat}
            selected={selected}
            locked={locked}
            manualWords={manualWords}
            manualInput={manualInput}
            onManualInputChange={setManualInput}
            onToggle={handleToggleWord}
            onManualAdd={handleManualAdd}
            loading={loading}
          />
        )}

        <div className="space-y-1.5 border-t border-neutral-200 pt-3 dark:border-neutral-800">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-500">
              提示词框（已选关键词）
            </span>
            <span className="font-mono text-[10px] text-neutral-400">
              已选 {selected.size} / 锁 {locked.size}
            </span>
          </div>
          <div className="min-h-[2.5rem] rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm leading-relaxed dark:border-neutral-800 dark:bg-neutral-900">
            {selected.size > 0 ? (
              Array.from(selected).join("、")
            ) : (
              <span className="text-neutral-400">（未选）</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
