/**
 * 步骤 3 · 大纲与人物。
 *
 * 对应设计稿 s11。大纲流式生成 → 自动抽取人物 → 逐张人物卡生成。
 *
 * 2026-10-25 的两个关键改动：
 *
 * 1. **不再显示 JSON 代码**。旧实现流式阶段把 LLM 吐的原始 JSON 用
 *    `<pre>` 直接渲染 —— 用户看到的是一堆英文代码（"把代码也显示出来"）。
 *    现在后端推的是**已解析好的结构**，流式和完成阶段共用
 *    :component:`OutlineStructureView`，从头到尾都是中文剧情。
 *
 * 2. **显示当前模型 + 耗时**。用户明确要求"添加生成当前模型耗时多少秒"。
 *    生成中显示实时秒数，完成后显示总耗时 + 首字延迟 + 模型名。
 */

import { useEffect, useMemo, useRef } from "react";
import { Check, Loader2, TriangleAlert } from "lucide-react";
import type { CharProgress, GenStats, NovelState } from "./types";
import type { OutlineVolumeStatus } from "@/stores/newbook-store";
import OutlineStructureView from "./outline-structure-view";
import type { OutlineMode } from "./outline-mode-picker";
import { isNearBottom, scrollToBottom } from "@/lib/auto-scroll";
import { checkOutlineCoverage, coveragePercent } from "@/lib/consistency";
import { cn } from "@/lib/utils";

interface Props {
  /** 当前阶段 */
  phase: "outline" | "characters" | "done";
  /** 流式过程中已解析出的**部分**大纲结构 */
  outlinePartial: Record<string, unknown> | null;
  /** 流式过程中已完成的章节数 */
  outlineChaptersDone: number;
  /**
   * 各卷细化状态（两阶段大纲的阶段二）。
   *
   * 骨架完成后各卷**并行**补细节 —— 用户要能看到"哪一卷好了"。
   */
  outlineVolumeStatus: Record<number, OutlineVolumeStatus>;
  /** 选中的那条剧情摘要（用于检测大纲是否沿着剧情走） */
  plotSummary: string;
  /** 模型思考中的文本（<think> 块）—— 有值且还没出正文时显示"模型思考中…" */
  outlineThinking: string;
  /** 大纲阶段是否正在生成（区分"生成中"与"上次被刷新打断"） */
  generating: boolean;
  /** 大纲完成后的结构（结构化渲染用） */
  outlineStructure: Record<string, unknown> | null;
  novelMeta: NovelState | null;
  charProgress: CharProgress;
  /** 人物卡阶段的思考提示 */
  charThinking: string;
  /** 大纲阶段的统计（模型 + 耗时 + 首字延迟） */
  outlineStats: GenStats | null;
  /** 人物卡阶段的统计（模型 + 耗时） */
  charStats: GenStats | null;
  /** 当前阶段已耗时（秒）—— 生成中实时显示 */
  elapsedSec: number;
  /** 本次用的大纲模式 */
  outlineMode: OutlineMode;
  /** 去写第一章 */
  onFinish: () => void;
  /** 退回剧情页重选一条 */
  onBack: () => void;
  /** 再写一本 */
  onRestart: () => void;
}

export default function OutlineStep({
  phase,
  outlinePartial,
  outlineChaptersDone,
  outlineVolumeStatus,
  plotSummary,
  generating,
  outlineThinking,
  outlineStructure,
  novelMeta,
  charProgress,
  charThinking,
  outlineStats,
  charStats,
  elapsedSec,
  outlineMode,
  onFinish,
  onBack,
  onRestart,
}: Props) {
  const savedCount = charProgress.cards.filter((c) => c.id).length;

  /** 流式结构区的 DOM 引用（用于自动滚到底部看最新章节） */
  const streamRef = useRef<HTMLDivElement | null>(null);

  // 流式内容变化 → 滚到底部看最新
  //
  // ⚠️ 只在"用户本来就在底部附近"时自动滚，避免把想回看的人强行拽下去。
  useEffect(() => {
    const el = streamRef.current;
    if (!el) return;
    if (isNearBottom(el)) scrollToBottom(el);
  }, [outlinePartial]);

  const modeLabel = outlineMode === "semi_open" ? "半开放式大纲" : "完整大纲";

  /**
   * 各卷名称（阶段二并行补细节时显示"哪一卷好了"）。
   *
   * 只在有状态数据时才渲染 —— 骨架还没出来时没必要占地方。
   */
  const volumeRows = (() => {
    const status = outlineVolumeStatus;
    if (Object.keys(status).length === 0) return [];
    const volumes = (outlinePartial?.volumes ?? []) as { name?: string }[];
    return volumes.map((v, i) => ({
      index: i,
      name: v.name ?? `第 ${i + 1} 卷`,
      status: status[i],
    }));
  })();

  /**
   * 大纲与剧情走向的**词面重合度**（需求6）。
   *
   * 用流式里的部分结构算（生成中就能看到实时变化）。
   */
  const plotCoverage = useMemo(
    () =>
      checkOutlineCoverage(
        phase === "outline" ? outlinePartial : outlineStructure,
        plotSummary,
      ),
    [phase, outlinePartial, outlineStructure, plotSummary],
  );

  return (
    <div>
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[19px] font-semibold tracking-tight">
            {phase === "done" ? "作品骨架已就绪" : "正在生成大纲与人物卡"}
          </h2>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-neutral-400">
            {phase === "outline"
              ? `${modeLabel}会按「卷 → 章 → 关键事件」结构化输出，随后自动抽取角色。`
              : phase === "characters"
                ? "大纲已完成，正在从大纲抽取角色并生成人物卡。"
                : "大纲与人物卡都已入库，可以直接开始写第一章。"}
          </p>
        </div>
        {/* 选错一条还能回头（否则只能整本重开） */}
        <button
          type="button"
          onClick={onBack}
          className="h-7 shrink-0 rounded-lg px-2.5 text-[12px] text-neutral-500 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
        >
          ← 换一条剧情
        </button>
      </div>

      {/* ===== 大纲 ===== */}
      <section className="mb-6 overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center gap-2 border-b border-neutral-200/70 px-3.5 py-2.5 dark:border-neutral-800/70">
          <h3 className="text-[12.5px] font-semibold">
            {novelMeta ? `《${novelMeta.name}》大纲` : "大纲"}
          </h3>
          {phase === "outline" ? (
            <span className="ml-auto inline-flex items-center gap-1.5 rounded bg-violet-500/15 px-1.5 py-0.5 text-[10.5px] text-violet-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              {outlineThinking && !outlinePartial
                ? `模型思考中… ${elapsedSec}s`
                : `流式生成中 ${elapsedSec}s`}
            </span>
          ) : (
            <span className="ml-auto inline-flex items-center gap-1 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10.5px] text-emerald-500">
              <Check className="h-3 w-3" />
              {outlineStats
                ? `已完成 · 用时 ${outlineStats.elapsedSec}s`
                : "已完成"}
            </span>
          )}
        </div>

        <div className="p-3.5">
          {phase === "outline" ? (
            outlinePartial || outlineStructure ? (
              /*
               * ⚠️ 必须是 `overflow-y-auto`（原来写的是 `overflow-hidden`）：
               *    内容流到边界就被裁掉 → 后面的字渲染了但**看不见** →
               *    用户看到"生成到一半不动了"。
               */
              <div ref={streamRef} className="max-h-[460px] overflow-y-auto">
                <OutlineStructureView
                  structure={outlinePartial ?? outlineStructure}
                  streaming={generating}
                  chaptersDone={outlineChaptersDone}
                />
              </div>
            ) : generating ? (
              <div className="flex items-center gap-2 rounded-lg border border-dashed border-neutral-200 px-3 py-3 text-[11.5px] text-neutral-400 dark:border-neutral-800">
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-violet-400" />
                {outlineThinking
                  ? `模型思考中… ${outlineThinking.slice(-40).trim()}`
                  : "正在构思卷章结构…"}
              </div>
            ) : (
              /* 刷新把生成打断了（outlinePartial 不持久化）—— 给明确出口 */
              <div className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 px-3 py-3 text-[11.5px] leading-relaxed text-amber-600 dark:text-amber-400">
                上次的大纲生成被中断了（刷新页面会打断生成）。
                <br />
                点右上角「← 换一条剧情」重新生成。
              </div>
            )
          ) : (
            <OutlineStructureView structure={outlineStructure} />
          )}
        </div>

        {/* 阶段二：各卷并行补细节的进度（哪一卷好了） */}
        {volumeRows.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-neutral-200/70 px-3.5 py-2 dark:border-neutral-800/70">
            <span className="text-[10.5px] text-neutral-400">细化各卷</span>
            {volumeRows.map((v) => (
              <span
                key={v.index}
                className={cn(
                  "inline-flex max-w-[180px] items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px]",
                  v.status === "done"
                    ? "bg-emerald-500/15 text-emerald-500"
                    : v.status === "error"
                      ? "bg-rose-500/15 text-rose-500"
                      : "bg-violet-500/15 text-violet-400",
                )}
              >
                {v.status === "done" ? (
                  <Check className="h-2.5 w-2.5 shrink-0" />
                ) : v.status === "error" ? (
                  <TriangleAlert className="h-2.5 w-2.5 shrink-0" />
                ) : (
                  <Loader2 className="h-2.5 w-2.5 shrink-0 animate-spin" />
                )}
                <span className="truncate">{v.name}</span>
              </span>
            ))}
          </div>
        ) : null}

        {/* 与剧情走向的重合度（需求6：检测大纲是否沿着选中的剧情走） */}
        {plotCoverage.total > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-neutral-200/70 px-3.5 py-2 text-[10.5px] text-neutral-400 dark:border-neutral-800/70">
            <span
              className={cn(
                "rounded px-1.5 py-0.5",
                coveragePercent(plotCoverage) >= 60
                  ? "bg-emerald-500/15 text-emerald-500"
                  : coveragePercent(plotCoverage) >= 35
                    ? "bg-amber-500/15 text-amber-500"
                    : "bg-rose-500/15 text-rose-500",
              )}
            >
              与剧情走向重合 {coveragePercent(plotCoverage)}%
            </span>
            {plotCoverage.matched.length > 0 ? (
              <span className="text-neutral-400">
                命中：{plotCoverage.matched.slice(0, 6).join("、")}
              </span>
            ) : null}
            {plotCoverage.missing.length > 0 ? (
              <span className="text-neutral-400">
                未覆盖：{plotCoverage.missing.slice(0, 6).join("、")}
                {plotCoverage.missing.length > 6 ? "…" : ""}
              </span>
            ) : null}
          </div>
        ) : null}

        {/* 生成信息：模型 + 耗时 */}
        {phase !== "outline" && outlineStats ? (
          <div className="border-t border-neutral-200/70 px-3.5 py-2 text-[11px] text-neutral-400 dark:border-neutral-800/70">
            {outlineStats.model || "当前模型"} · 大纲用时 {outlineStats.elapsedSec}s
            {outlineStats.firstDeltaSec != null
              ? ` · 首字 ${outlineStats.firstDeltaSec}s`
              : ""}
          </div>
        ) : null}
      </section>

      {/* ===== 人物卡 ===== */}
      {phase !== "outline" ? (
        <section className="mb-6">
          <div className="mb-2.5 flex items-center gap-2">
            <h3 className="flex items-baseline gap-2 text-[12.5px] font-semibold">
              人物卡
              <span className="text-[11.5px] font-normal text-neutral-400">
                从大纲自动抽取 · {charProgress.extracted.length} 个角色
              </span>
            </h3>
            {phase === "characters" ? (
              <span className="ml-auto rounded bg-violet-500/15 px-1.5 py-0.5 text-[10.5px] text-violet-400">
                生成 {savedCount} / {charProgress.extracted.length} · {elapsedSec}s
              </span>
            ) : null}
          </div>

          {charProgress.cards.length === 0 ? (
            <p className="rounded-lg border border-dashed border-neutral-200 px-3 py-3 text-[11.5px] text-neutral-400 dark:border-neutral-800">
              {charThinking
                ? `模型思考中… ${charThinking.slice(-40).trim()}`
                : "正在从大纲抽取角色…"}
            </p>
          ) : (
            <div className="flex flex-wrap gap-2.5">
              {charProgress.cards.map((c) => (
                <div
                  key={c.name}
                  className={cn(
                    "w-[104px] rounded-xl border p-2.5 text-center",
                    c.id !== undefined
                      ? "border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
                      : "border-dashed border-neutral-300 dark:border-neutral-700",
                  )}
                >
                  <div
                    className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-xl text-[16px] font-semibold text-white"
                    style={{
                      background: `linear-gradient(150deg,#${(c.name.charCodeAt(0) * 137) % 4096}, #${(c.name.charCodeAt(0) * 331) % 4096})`,
                    }}
                  >
                    {c.name.slice(0, 1)}
                  </div>
                  <div className="truncate text-[11.5px] font-semibold">
                    {c.name}
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-neutral-400">
                    {c.role}
                  </div>
                  <div className="mt-2 h-0.5 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700">
                    <i
                      className={cn(
                        "block h-full rounded-full",
                        c.id !== undefined ? "bg-emerald-500" : "bg-violet-500",
                      )}
                      style={{ width: c.id !== undefined ? "100%" : "60%" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {charStats ? (
            <p className="mt-2 text-[11px] text-neutral-400">
              {charStats.model || "当前模型"} · 人物卡用时 {charStats.elapsedSec}s
            </p>
          ) : null}

          {charProgress.error ? (
            <p className="mt-2 text-[11.5px] text-rose-500">{charProgress.error}</p>
          ) : null}
        </section>
      ) : null}

      {/* ===== 完成卡 ===== */}
      {phase === "done" ? (
        <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/10 to-transparent p-4">
          <h4 className="flex items-center gap-2 text-[15px] font-semibold">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-500/15">
              <Check className="h-3.5 w-3.5 text-emerald-500" />
            </span>
            《{novelMeta?.name}》已就绪
          </h4>
          <p className="mt-1.5 text-[12.5px] text-neutral-500 dark:text-neutral-400">
            {modeLabel} · {savedCount} 个人物卡
            {outlineStats ? ` · 大纲用时 ${outlineStats.elapsedSec}s` : ""}
            {charStats ? ` · 人物卡用时 ${charStats.elapsedSec}s` : ""}
          </p>
          <div className="mt-4 flex gap-2.5">
            <button
              type="button"
              onClick={onFinish}
              className="inline-flex h-8 items-center rounded-lg bg-indigo-600 px-4 text-[12.5px] font-medium text-white transition-colors hover:bg-indigo-700"
            >
              去写第一章 →
            </button>
            <button
              type="button"
              onClick={onRestart}
              className="inline-flex h-8 items-center rounded-lg border border-neutral-200 px-4 text-[12.5px] text-neutral-600 transition-colors hover:bg-neutral-100 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              再写一本
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
