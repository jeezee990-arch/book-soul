/**
 * 素材选择器：从素材库里挑素材接入到聊天项目（2026-10-25 新增）。
 *
 * 为什么需要
 * ----------
 * 「项目可以从素材库选择素材进行接入」——
 * 接入的素材会进 system prompt，模型讨论时就知道这些设定/片段。
 *
 * 交互：弹层 + 复选框 + 全选/清空 + 保存。
 */

import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { inspirationsApi } from "@/api/inspirations";
import type { Inspiration } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  /** 已接入的素材 id */
  selected: number[];
  onClose: () => void;
  onSave: (ids: number[]) => void | Promise<void>;
}

/** 素材内容 → 一行可读摘要。 */
function summarize(content: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const key of ["title", "summary", "text", "content"]) {
    const v = content[key];
    if (typeof v === "string" && v.trim()) {
      parts.push(v.trim());
      break;
    }
  }
  if (parts.length === 0) {
    const v = content.summary ?? content.text ?? content.title;
    if (typeof v === "string") parts.push(v.trim());
  }
  const text = parts.join(" ");
  return text.length > 90 ? `${text.slice(0, 90)}…` : text || "（无内容）";
}

export default function MaterialPicker({
  open,
  selected,
  onClose,
  onSave,
}: Props) {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState<number[]>(selected);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPicked(selected);
    setLoading(true);
    inspirationsApi
      .list()
      .then((rows) => setItems(rows))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
    // 只在打开时拉一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  const toggle = (id: number) => {
    setPicked((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-6"
      onClick={onClose}
    >
      <div
        className="flex max-h-[70vh] w-[560px] flex-col overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-xl dark:border-neutral-800 dark:bg-neutral-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-neutral-200 px-3.5 py-2.5 dark:border-neutral-800">
          <span className="text-[13px] font-semibold">从素材库接入</span>
          <span className="text-[11.5px] text-neutral-400">
            已选 {picked.length} 项
          </span>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
            title="关闭"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-2 border-b border-neutral-200/70 px-3.5 py-1.5 dark:border-neutral-800/70">
          <button
            type="button"
            onClick={() => setPicked(items.map((i) => i.id))}
            className="rounded px-1.5 py-0.5 text-[11px] text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            全选
          </button>
          <button
            type="button"
            onClick={() => setPicked([])}
            className="rounded px-1.5 py-0.5 text-[11px] text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            清空
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-[12px] text-neutral-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              读取素材库…
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-[12px] text-neutral-400">
              素材库还是空的 —— 先去「素材库」记点东西
            </p>
          ) : (
            items.map((item) => {
              const on = picked.includes(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => toggle(item.id)}
                  className={cn(
                    "mb-1 flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors",
                    on
                      ? "bg-indigo-500/10"
                      : "hover:bg-neutral-100 dark:hover:bg-neutral-800",
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 grid h-3.5 w-3.5 shrink-0 place-items-center rounded border",
                      on
                        ? "border-indigo-500 bg-indigo-500 text-white"
                        : "border-neutral-300 dark:border-neutral-600",
                    )}
                  >
                    {on ? <Check className="h-2.5 w-2.5" /> : null}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[11px] text-neutral-400">
                      {item.type}
                    </span>
                    <span className="block truncate text-[12px] text-neutral-600 dark:text-neutral-300">
                      {summarize(item.content)}
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-neutral-200 px-3.5 py-2.5 dark:border-neutral-800">
          <button
            type="button"
            onClick={onClose}
            className="h-7 rounded-lg px-3 text-[12px] text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            取消
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={async () => {
              setSaving(true);
              try {
                await onSave(picked);
                onClose();
              } finally {
                setSaving(false);
              }
            }}
            className="inline-flex h-7 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-[12px] font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            接入 {picked.length} 项
          </button>
        </div>
      </div>
    </div>
  );
}
