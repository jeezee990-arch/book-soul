/**
 * 大纲模式选择（2026-10-25 新增）。
 *
 * 两种模式（用户规划）：
 *
 * - **完整大纲**：从小说开头直接生成到全书结束。**适合短篇小说** ——
 *   一次成型，作者不用再管结构。
 * - **半开放式**：只生成前期（留悬念）的大纲，后续由作者自行创作，
 *   或用 AI 辅助续写。适合长篇连载 —— 保留作者对中后期的掌控。
 *
 * 用卡片式单选而不是下拉框：两个选项的差别是**创作方式**的差别，
 * 需要各自说清楚适用场景，下拉框放不下这些说明。
 */

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/** 大纲模式（与后端 `outline_type` 一致）。 */
export type OutlineMode = "complete" | "semi_open";

interface Option {
  value: OutlineMode;
  title: string;
  badge?: string;
  desc: string;
  detail: string;
}

const OPTIONS: Option[] = [
  {
    value: "complete",
    title: "完整大纲",
    badge: "适合短篇小说",
    desc: "从开头一直写到全书结束",
    detail:
      "一次性给出全部分卷与章节，故事走向完整、结局明确。适合短篇或已经想清楚全貌的作品。",
  },
  {
    value: "semi_open",
    title: "半开放式",
    badge: "适合长篇连载",
    desc: "只写前期，留下悬念",
    detail:
      "只铺开前期的卷章并停在一个关键转折上，后面留给你 —— 可以自己续写，也可以让 AI 基于悬念继续生成。",
  },
];

interface Props {
  value: OutlineMode;
  onChange: (value: OutlineMode) => void;
  /** 生成中时禁用选择 */
  disabled?: boolean;
}

export default function OutlineModePicker({ value, onChange, disabled = false }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2.5">
      {OPTIONS.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-xl border p-3 text-left transition-all",
              active
                ? "border-indigo-500 bg-indigo-500/[0.06] shadow-[0_0_0_3px_rgba(99,102,241,.10)]"
                : "border-neutral-200 hover:border-neutral-300 dark:border-neutral-800 dark:hover:border-neutral-700",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "text-[12.5px] font-semibold",
                  active ? "text-indigo-600 dark:text-indigo-400" : "",
                )}
              >
                {opt.title}
              </span>
              {opt.badge ? (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px]",
                    active
                      ? "bg-indigo-500/15 text-indigo-500"
                      : "bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400",
                  )}
                >
                  {opt.badge}
                </span>
              ) : null}
              {active ? (
                <Check className="ml-auto h-3.5 w-3.5 text-indigo-500" />
              ) : null}
            </div>
            <p className="mt-1 text-[11.5px] font-medium text-neutral-600 dark:text-neutral-300">
              {opt.desc}
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-neutral-400">{opt.detail}</p>
          </button>
        );
      })}
    </div>
  );
}
