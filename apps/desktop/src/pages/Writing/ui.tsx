/**
 * 写作页右栏的小型复用 UI（字段、段落标题、分段控件、提示条、流式输出框）。
 *
 * 单独抽出来是因为 6 个 Tab 都在用同样的排版节奏，
 * 内联复制会让每个 Tab 都多出 30 行样式代码。
 */

import { useEffect, useRef, type ReactNode } from "react";
import { Brain } from "lucide-react";
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

/**
 * 流式输出框（**可滚动 + 自动滚到底**）。
 *
 * ⚠️ 为什么不能写 ``overflow-hidden``（AGENTS.md §4.7 铁律）：
 * 内容区固定高度 + 裁掉溢出 → 文字流到边界就被裁掉，
 * 后面的字渲染了但**看不见** → 用户看到"生成到一半不动了"，
 * 结束时又"一口气全出来"。必须能滚 + 自动跟随底部。
 */
export function StreamBox({
  text,
  tail = 1200,
  className,
}: {
  /** 累积的正文 */
  text: string;
  /** 只显示末尾多少字（正文很长时避免 DOM 过大） */
  tail?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // 每次内容变化都滚到底部（用户正在看最新的一段）
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [text]);

  return (
    <div
      ref={ref}
      className={cn(
        "overflow-y-auto font-serif text-[13px] leading-relaxed text-neutral-300",
        className,
      )}
    >
      {text.slice(-tail)}
      <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-400 align-middle" />
    </div>
  );
}

/**
 * 模型思考提示框。
 *
 * 推理模型（MiniMax M3 等）先吐好几秒 ``<think>`` 再写正文。
 * 这段时间如果什么都不显示，用户看到的就是"卡住不动"。
 * 思考内容单独显示在正文框上方（正文区保持干净，不混进英文思考）。
 */
export function ThinkingBox({ text }: { text: string }) {
  if (!text.trim()) return null;
  return (
    <div className="mb-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-2.5 py-2">
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-300">
        <Brain className="h-3.5 w-3.5" />
        模型思考中
      </div>
      <p className="max-h-[72px] overflow-y-auto text-[11px] leading-relaxed text-neutral-500 dark:text-neutral-400">
        {text.slice(-400)}
      </p>
    </div>
  );
}
