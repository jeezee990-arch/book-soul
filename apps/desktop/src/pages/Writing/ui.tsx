/**
 * 写作页右栏的小型复用 UI（字段、段落标题、分段控件、提示条）。
 *
 * 单独抽出来是因为 6 个 Tab 都在用同样的排版节奏，
 * 内联复制会让每个 Tab 都多出 30 行样式代码。
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** 分段控件（单选）。 */
export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex gap-0.5 rounded-lg border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-800/40",
        className,
      )}
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "flex-1 rounded-md px-1.5 py-1.5 text-[11.5px] transition-colors",
            value === o.value
              ? "bg-white font-medium text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-neutral-50"
              : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** 表单字段（标签 + 内容）。 */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mb-3.5">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-[11.5px] text-neutral-600 dark:text-neutral-400">
          {label}
        </span>
        {hint ? (
          <span className="text-[10.5px] text-neutral-400">{hint}</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

/** 段落小标题。 */
export function SectionLabel({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <span className="text-[10.5px] font-semibold tracking-[0.07em] text-neutral-400 uppercase">
        {children}
      </span>
      {action}
    </div>
  );
}

/** 提示条。 */
export function HintBar({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn" | "error" | "ai";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    info: "border-neutral-200 bg-neutral-50 text-neutral-500 dark:border-neutral-800 dark:bg-neutral-800/40",
    warn: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-300",
    error: "border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-300",
    ai: "border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-300",
  };
  return (
    <div
      className={cn(
        "rounded-lg border px-2.5 py-2 text-[11px] leading-relaxed",
        tones[tone],
      )}
    >
      {children}
    </div>
  );
}

/** 右栏内输入框（统一高度 / 圆角 / 深浅色）。 */
export const panelInputClass =
  "w-full rounded-lg border border-neutral-200 bg-neutral-50 px-2.5 py-2 text-[12.5px] text-neutral-900 placeholder:text-neutral-400 focus:border-indigo-500/60 focus:outline-none focus:ring-2 focus:ring-indigo-500/15 dark:border-neutral-800 dark:bg-neutral-800/40 dark:text-neutral-100";
