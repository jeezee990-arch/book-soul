import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * 关键词面板的"分类 tab + 词条网格 + 手动添加"段（Phase 3.2）。
 * 纯展示 + 交互透传，状态由父组件管。
 */
interface Props {
  categories: string[];
  activeCat: string | null;
  onChangeActive: (cat: string) => void;
  wordsByCat: Record<string, string[]>;
  selected: Set<string>;
  locked: Set<string>;
  manualWords: string[];
  manualInput: string;
  onManualInputChange: (v: string) => void;
  onToggle: (w: string) => void;
  onManualAdd: () => void;
  loading: boolean;
}

export default function WordSection({
  categories,
  activeCat,
  onChangeActive,
  wordsByCat,
  selected,
  locked,
  manualWords,
  manualInput,
  onManualInputChange,
  onToggle,
  onManualAdd,
  loading,
}: Props) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        onManualAdd();
      }
    },
    [onManualAdd],
  );

  return (
    <div className="space-y-3">
      {/* 分类 tab */}
      <div className="flex flex-wrap gap-1.5 border-b border-neutral-200 pb-2 dark:border-neutral-800">
        {categories.map((c) => {
          const isActive = activeCat === c;
          const total = (wordsByCat[c] ?? []).length;
          const selInCat = (wordsByCat[c] ?? []).filter((w) =>
            selected.has(w),
          ).length;
          return (
            <button
              key={c}
              type="button"
              onClick={() => onChangeActive(c)}
              className={[
                "rounded-md px-2.5 py-1 font-mono text-xs transition-colors",
                isActive
                  ? "bg-neutral-900 text-neutral-50 dark:bg-neutral-100 dark:text-neutral-900"
                  : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800",
              ].join(" ")}
            >
              {c} · {selInCat}/{total}
            </button>
          );
        })}
      </div>

      {/* 当前分类的词条 */}
      {activeCat && (
        <div className="space-y-3">
          {loading && <p className="text-xs text-neutral-400">加载中…</p>}
          <div className="flex flex-wrap gap-1.5">
            {(wordsByCat[activeCat] ?? []).map((w) => {
              const isSel = selected.has(w);
              const isLock = locked.has(w);
              return (
                <button
                  key={w}
                  type="button"
                  onClick={() => onToggle(w)}
                  className={[
                    "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",
                    isSel
                      ? "border-neutral-900 bg-neutral-900 text-neutral-50 dark:border-neutral-100 dark:bg-neutral-100 dark:text-neutral-900"
                      : "border-neutral-200 text-neutral-700 hover:bg-neutral-50 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-900",
                  ].join(" ")}
                >
                  {isLock && <span aria-label="locked">🔒</span>}
                  <span>{w}</span>
                </button>
              );
            })}
            {(wordsByCat[activeCat] ?? []).length === 0 && !loading && (
              <p className="text-xs text-neutral-400">（该分类暂无词）</p>
            )}
          </div>

          {/* 手动添加的词（跨分类，单独一段） */}
          {manualWords.length > 0 && (
            <div className="border-t border-dashed border-neutral-200 pt-3 dark:border-neutral-800">
              <div className="mb-1.5 text-[10px] uppercase tracking-wider text-neutral-400">
                手动添加
              </div>
              <div className="flex flex-wrap gap-1.5">
                {manualWords.map((w) => {
                  const isSel = selected.has(w);
                  return (
                    <button
                      key={w}
                      type="button"
                      onClick={() => onToggle(w)}
                      className={[
                        "inline-flex items-center rounded-md border px-2 py-1 text-xs transition-colors",
                        isSel
                          ? "border-neutral-900 bg-neutral-900 text-neutral-50 dark:border-neutral-100 dark:bg-neutral-100 dark:text-neutral-900"
                          : "border-neutral-200 text-neutral-700 hover:bg-neutral-50 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-900",
                      ].join(" ")}
                    >
                      {w}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 手动添加输入 */}
      <div className="flex items-center gap-2 border-t border-neutral-200 pt-3 dark:border-neutral-800">
        <span className="shrink-0 text-xs text-neutral-500">手动添加：</span>
        <Input
          type="text"
          placeholder="输入灵感词后回车或点 +"
          value={manualInput}
          onChange={(e) => onManualInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1"
        />
        <Button
          size="sm"
          variant="outline"
          onClick={onManualAdd}
          disabled={!manualInput.trim()}
        >
          +
        </Button>
      </div>
    </div>
  );
}
