/**
 * 种子库管理的词条列表（按分类分组）。
 *
 * 单独抽出来是因为列表区（含每行的编辑 / 删除 / 勾选）是这个弹窗里最大的一块，
 * 放在弹窗文件里会让文件超过 500 行。
 */

import { Check, Pencil, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { WordbankAllWords } from "@/lib/types";
import { categoryLabel } from "./wordbank-parse";
import { wordKey } from "./wordbank-selection";

interface Props {
  /** 当前板块的全部词条 */
  data: WordbankAllWords;
  loading: boolean;
  /** 管理模式（显示勾选框） */
  manage: boolean;
  /** 已勾选的词条 key */
  selected: ReadonlySet<string>;
  /** 正在编辑的行 */
  editing: { category: string; word: string } | null;
  /** 编辑框里的值 */
  editValue: string;
  /** 有写操作在进行中（禁用按钮） */
  busy: boolean;
  onToggleSelect: (key: string) => void;
  onStartEdit: (category: string, word: string) => void;
  onEditValueChange: (value: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onDelete: (category: string, word: string) => void;
}

export default function WordbankManagerList({
  data,
  loading,
  manage,
  selected,
  editing,
  editValue,
  busy,
  onToggleSelect,
  onStartEdit,
  onEditValueChange,
  onSaveEdit,
  onCancelEdit,
  onDelete,
}: Props) {
  if (loading) {
    return <p className="p-3 text-[11.5px] text-neutral-400">加载中…</p>;
  }
  if (data.categories.length === 0) {
    return <p className="p-3 text-[11.5px] text-neutral-400">这个板块还没有词条</p>;
  }

  return (
    <>
      {data.categories.map((cat) => {
        const words = data.words[cat] ?? [];
        return (
          <section
            key={cat}
            className="border-b border-neutral-100 last:border-0 dark:border-neutral-900"
          >
            <header className="sticky top-0 flex items-baseline gap-2 bg-neutral-50/95 px-3 py-1.5 backdrop-blur dark:bg-neutral-900/95">
              <span className="text-[11.5px] font-semibold">{categoryLabel(cat)}</span>
              <span className="text-[10.5px] text-neutral-400">{words.length} 个</span>
            </header>
            {words.length === 0 ? (
              <p className="px-3 py-1.5 text-[11px] text-neutral-400 italic">（空）</p>
            ) : (
              words.map((word) => {
                const key = wordKey(cat, word);
                const isEditing = editing?.category === cat && editing?.word === word;
                return (
                  <div
                    key={key}
                    className="group flex items-center gap-2 px-3 py-1 hover:bg-neutral-50 dark:hover:bg-neutral-900"
                  >
                    {manage ? (
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 shrink-0 accent-indigo-500"
                        checked={selected.has(key)}
                        onChange={() => onToggleSelect(key)}
                        aria-label={"选择 " + word}
                      />
                    ) : null}
                    {isEditing ? (
                      <>
                        <input
                          value={editValue}
                          autoFocus
                          onChange={(e) => onEditValueChange(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") onSaveEdit();
                            if (e.key === "Escape") onCancelEdit();
                          }}
                          className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                        <button
                          type="button"
                          onClick={onSaveEdit}
                          disabled={busy}
                          className="text-indigo-500 hover:text-indigo-600"
                          aria-label="保存"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={onCancelEdit}
                          className="text-neutral-400 hover:text-neutral-600"
                          aria-label="取消"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="flex-1 truncate text-[12px]">{word}</span>
                        <button
                          type="button"
                          onClick={() => onStartEdit(cat, word)}
                          className={cn(
                            "text-neutral-300 opacity-0 transition-opacity hover:text-indigo-500 focus-visible:opacity-100 group-hover:opacity-100",
                            "dark:text-neutral-600",
                          )}
                          aria-label={"编辑 " + word}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onDelete(cat, word)}
                          disabled={busy}
                          className={cn(
                            "text-neutral-300 opacity-0 transition-opacity hover:text-rose-500 focus-visible:opacity-100 group-hover:opacity-100",
                            "dark:text-neutral-600",
                          )}
                          aria-label={"删除 " + word}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                );
              })
            )}
          </section>
        );
      })}
    </>
  );
}
