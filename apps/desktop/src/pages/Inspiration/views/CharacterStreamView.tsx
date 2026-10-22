/**
 * 人物卡生成视图。
 *
 * 每张卡边生成边显示（`card_delta` 追加文本），入库后显示 `#id`。
 */

import { Button } from "@/components/ui/button";
import type { CharProgress, NovelState } from "../types";

/** 人物卡生成中的界面。 */
export default function CharacterStreamView({
  progress,
  novelMeta,
  onBack,
}: {
  progress: CharProgress;
  novelMeta: NovelState | null;
  onBack: () => void;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">正在生成人物卡...</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            {novelMeta?.name && `《${novelMeta.name}》`} · 已抽取 {progress.extracted.length} 人
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 取消
        </Button>
      </header>

      <div className="space-y-3">
        {progress.cards.map((c) => (
          <div
            key={c.name}
            className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{c.name}</span>
                <span className="text-xs text-neutral-400">· {c.role}</span>
              </div>
              {c.id !== undefined ? (
                <span className="text-xs text-indigo-600 dark:text-indigo-400">
                  ✓ 已入库 (#{c.id})
                </span>
              ) : (
                <span className="text-xs text-neutral-400 animate-pulse">生成中…</span>
              )}
            </div>
            {c.text && (
              <pre className="text-xs leading-relaxed font-mono whitespace-pre-wrap text-neutral-700 dark:text-neutral-300 max-h-48 overflow-y-auto">
                {c.text}
              </pre>
            )}
          </div>
        ))}
      </div>
      {progress.error && (
        <p className="text-xs text-destructive">{progress.error}</p>
      )}
    </div>
  );
}
