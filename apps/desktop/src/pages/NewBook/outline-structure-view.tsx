/**
 * 大纲的结构化渲染（卷 → 章 → 关键事件）。
 *
 * 为什么单独抽一个组件（2026-10-25）
 * ----------------------------------
 * 旧实现里，流式阶段把 LLM 吐的**原始 JSON** 用 `<pre>` 直接显示 ——
 * 用户看到的是一堆英文代码（反馈里说的"把代码也显示出来"）。
 * 完成之后才切换成结构化渲染（卷 → 章）。
 *
 * 现在后端改推**已解析好的结构**（`partial` / `done` 事件里的 `structure`），
 * 流式阶段和完成阶段共用这一个组件 —— 用户从头到尾看到的都是中文剧情，
 * 而且流式过程中就能看到"已写完的那几章"，不再是黑箱。
 */

import type { SemiOpenOutlineStructure } from "@/lib/types";

interface Props {
  /** 已解析的大纲结构（complete / semi_open 形状） */
  structure: Record<string, unknown> | null;
  /** 是否还在流式生成中（显示"正在铺开…"和进度） */
  streaming?: boolean;
  /** 已完成的章节数（流式进度提示用） */
  chaptersDone?: number;
}

export default function OutlineStructureView({
  structure,
  streaming = false,
  chaptersDone = 0,
}: Props) {
  const parsed = structure as SemiOpenOutlineStructure | null;
  const volumes = parsed?.volumes ?? [];

  if (volumes.length === 0) {
    return (
      <p className="text-[12px] text-neutral-400">
        {streaming ? "正在铺开卷章结构…" : "大纲已生成（自由型）"}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {parsed?.overall_theme ? (
        <p className="rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-[12px] text-violet-600 dark:text-violet-300">
          <b className="font-semibold">全篇主题</b>：{parsed.overall_theme}
        </p>
      ) : null}

      {/* 半开放式特有：大纲在此停下，留一个悬念给作者 */}
      {parsed?.suspense_hook ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2.5">
          <p className="text-[11.5px] font-semibold text-amber-600 dark:text-amber-400">
            悬念钩子 · 大纲在此停下
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-amber-700/90 dark:text-amber-300/90">
            {parsed.suspense_hook}
          </p>
        </div>
      ) : null}

      {volumes.map((v, vi) => (
        <div
          key={`${v.name}-${vi}`}
          className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800"
        >
          <div className="flex items-center gap-2 bg-neutral-100 px-3 py-2 dark:bg-neutral-800/60">
            <span className="text-[12px] font-semibold">{v.name}</span>
            <span className="ml-auto text-[10.5px] text-neutral-400">
              {v.chapters?.length ?? 0} 章
            </span>
          </div>

          {v.summary ? (
            <p className="border-t border-neutral-200 px-3 py-2 text-[11.5px] leading-relaxed text-neutral-500 dark:border-neutral-800 dark:text-neutral-400">
              {v.summary}
            </p>
          ) : null}

          {(v.chapters ?? []).map((c, i) => (
            <div
              key={`${v.name}-${i}`}
              className="border-t border-neutral-200 px-3 py-2 dark:border-neutral-800"
            >
              <div className="flex items-start gap-2">
                <span className="mt-px font-mono text-[10.5px] text-violet-400">
                  CH{String(i + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1 text-[12px] font-medium">{c.title}</span>
              </div>
              {c.summary ? (
                <p className="mt-1 pl-[46px] text-[11.5px] leading-relaxed text-neutral-500 dark:text-neutral-400">
                  {c.summary}
                </p>
              ) : null}
              {c.key_events && c.key_events.length > 0 ? (
                <ul className="mt-1 space-y-0.5 pl-[46px]">
                  {c.key_events.map((e, ei) => (
                    <li key={ei} className="text-[11px] leading-relaxed text-neutral-400">
                      · {e}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
        </div>
      ))}

      {streaming && chaptersDone > 0 ? (
        <p className="text-center text-[11px] text-neutral-400">
          已生成 {chaptersDone} 章 · 还在继续…
        </p>
      ) : null}
    </div>
  );
}
