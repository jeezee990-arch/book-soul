/**
 * 质检 Tab：5 维度评分 + 一键重写闭环。
 *
 * 相比旧的一级质检页的两个变化：
 * 1. 报告渲染从"雷达图"改成"横向评分条" —— 332px 窄栏放雷达图看不清
 * 2. 每条问题可以直接「重写这段」→ 带着问题描述跳到重写 Tab
 *    （这是本次重设计新增的关键闭环：问题不留 in 报告，直接被修掉）
 */

import { useState } from "react";
import { AlertTriangle, ChevronDown, Loader2, Sparkles, Wand2 } from "lucide-react";
import { qualityApi, type QualityReport } from "@/api/quality";
import { ApiError } from "@/api";
import type { Chapter, Novel } from "@/lib/types";
import { HintBar, SectionLabel } from "../ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const DIMENSION_LABELS: Record<string, string> = {
  writing: "文笔",
  logic: "逻辑",
  pacing: "节奏",
  consistency: "一致性",
  genre: "题材合规",
};

/** 分数 → 颜色 */
function scoreTone(score: number): string {
  if (score >= 8) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 6) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
}

function barTone(score: number): string {
  if (score >= 8) return "bg-emerald-500";
  if (score >= 6) return "bg-amber-500";
  return "bg-rose-500";
}

interface Props {
  novel: Novel | null;
  chapter: Chapter | null;
  /** 从问题跳到重写（带预填指令） */
  onRewriteFromQuality: (suggestion: string) => void;
}

export default function QualityTab({ novel, chapter, onRewriteFromQuality }: Props) {
  const [report, setReport] = useState<QualityReport | null>(null);
  const [checking, setChecking] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCheck() {
    if (!novel || !chapter) return;
    setChecking(true);
    setReport(null);
    setExpanded(null);
    setError(null);
    try {
      const r = await qualityApi.check(novel.id, chapter.id);
      setReport(r);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setError(msg);
    } finally {
      setChecking(false);
    }
  }

  if (!novel || !chapter) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        先在左边选一个章节
      </div>
    );
  }

  if (chapter.word_count === 0) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        这一章还没有正文，先去「生成」写点内容
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="min-h-0 flex-1 px-3.5 py-3.5">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div>
            <h4 className="text-[12.5px] font-semibold">质检报告</h4>
            <p className="mt-0.5 text-[11.5px] text-neutral-400">
              5 维度并行评分 · 约 10–30s
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 shrink-0 px-2.5 text-[11.5px]"
            onClick={() => void handleCheck()}
            disabled={checking}
          >
            {checking ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                评分中
              </>
            ) : (
              <>
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                {report ? "重新检测" : "开始检测"}
              </>
            )}
          </Button>
        </div>

        {error ? (
          <HintBar tone="error">检测失败：{error}</HintBar>
        ) : null}

        {checking ? (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-9 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800/60"
              />
            ))}
          </div>
        ) : null}

        {!checking && !report && !error ? (
          <div className="py-8 text-center text-[12px] text-neutral-400">
            点「开始检测」跑一次质检
          </div>
        ) : null}

        {report ? (
          <>
            {/* 总分 + 维度条 */}
            <div className="mb-3.5 rounded-xl border border-neutral-200 bg-neutral-50 p-3 dark:border-neutral-800 dark:bg-neutral-800/40">
              <div className="mb-2.5 flex items-baseline gap-2">
                <span
                  className={cn(
                    "font-mono text-[30px] leading-none font-bold",
                    scoreTone(report.total_score),
                  )}
                >
                  {report.total_score.toFixed(1)}
                </span>
                <span className="text-[11px] text-neutral-400">/ 10 综合</span>
                <span className="ml-auto text-right text-[10px] leading-tight text-neutral-400">
                  {report.genre}
                  <br />
                  {report.provider}/{report.model}
                </span>
              </div>
              <div className="space-y-1.5">
                {Object.entries(report.dimension_scores).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 text-[11px]">
                    <span className="w-11 shrink-0 text-neutral-500 dark:text-neutral-400">
                      {DIMENSION_LABELS[k] ?? k}
                    </span>
                    <span className="h-1 flex-1 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700">
                      <i
                        className={cn("block h-full rounded-full", barTone(v))}
                        style={{ width: `${Math.min(100, v * 10)}%` }}
                      />
                    </span>
                    <span
                      className={cn(
                        "w-7 shrink-0 text-right font-mono",
                        scoreTone(v),
                      )}
                    >
                      {v.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* 问题列表（可一键重写） */}
            <SectionLabel>发现 {report.issues.length} 个问题</SectionLabel>
            {report.issues.length === 0 ? (
              <HintBar tone="info">没有明显问题 ✨</HintBar>
            ) : (
              <div className="space-y-2">
                {report.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-neutral-200 bg-neutral-50 p-2.5 dark:border-neutral-800 dark:bg-neutral-800/40"
                  >
                    <div className="mb-1.5 flex items-center gap-1.5">
                      <span className="rounded bg-rose-500/15 px-1.5 py-0.5 text-[10px] text-rose-500">
                        {DIMENSION_LABELS[issue.type] ?? issue.type}
                      </span>
                      {issue.character ? (
                        <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[10px] text-violet-400">
                          {issue.character}
                        </span>
                      ) : null}
                    </div>
                    {issue.quote ? (
                      <blockquote className="mb-1.5 border-l-2 border-neutral-300 pl-2 font-serif text-[11.5px] leading-relaxed text-neutral-500 italic dark:border-neutral-700 dark:text-neutral-400">
                        {issue.quote}
                      </blockquote>
                    ) : null}
                    {issue.problem ? (
                      <p className="mb-1.5 text-[11.5px] leading-relaxed text-rose-500">
                        {issue.problem}
                      </p>
                    ) : null}
                    {issue.suggestion ? (
                      <div className="flex items-start gap-2">
                        <p className="flex-1 text-[11px] leading-relaxed text-emerald-600 dark:text-emerald-400">
                          {issue.suggestion}
                        </p>
                        <Button
                          size="sm"
                          className="h-6 shrink-0 bg-violet-600 px-2 text-[10.5px] text-white hover:bg-violet-700"
                          onClick={() =>
                            onRewriteFromQuality(
                              issue.suggestion || issue.problem || "重写这段",
                            )
                          }
                        >
                          <Wand2 className="mr-1 h-3 w-3" />
                          重写这段
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            )}

            {/* 维度详情（折叠） */}
            <SectionLabel>维度详情</SectionLabel>
            <div className="space-y-1">
              {report.dimension_results.map((r) => {
                const open = expanded === r.dimension;
                return (
                  <div
                    key={r.dimension}
                    className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800"
                  >
                    <button
                      type="button"
                      onClick={() => setExpanded(open ? null : r.dimension)}
                      className="flex w-full items-center justify-between px-2.5 py-2 text-left transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-800/50"
                    >
                      <span className="flex items-center gap-1.5">
                        <span className="text-[12px] font-medium">
                          {DIMENSION_LABELS[r.dimension] ?? r.dimension}
                        </span>
                        {r.error ? (
                          <span className="text-[10px] text-rose-500">评分失败</span>
                        ) : (
                          <span className="text-[10px] text-neutral-400">
                            {r.issues.length} 问题 · {r.suggestions.length} 建议
                          </span>
                        )}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span
                          className={cn(
                            "font-mono text-[14px] font-semibold",
                            scoreTone(r.score),
                          )}
                        >
                          {r.score.toFixed(1)}
                        </span>
                        <ChevronDown
                          className={cn(
                            "h-3.5 w-3.5 text-neutral-400 transition-transform",
                            open && "rotate-180",
                          )}
                        />
                      </span>
                    </button>
                    {open ? (
                      <div className="space-y-1.5 border-t border-neutral-200 bg-neutral-50/60 px-2.5 py-2 dark:border-neutral-800 dark:bg-neutral-800/25">
                        {r.error ? (
                          <p className="text-[11px] text-rose-500">错误：{r.error}</p>
                        ) : null}
                        {r.issues.length === 0 && !r.error ? (
                          <p className="text-[11px] text-neutral-400">没有明显问题 ✨</p>
                        ) : null}
                        {r.suggestions.map((s, i) => (
                          <p
                            key={i}
                            className="text-[11px] leading-relaxed text-neutral-500 dark:text-neutral-400"
                          >
                            · {s}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            {report.suggestions.length > 0 ? (
              <>
                <SectionLabel>整体建议</SectionLabel>
                <ul className="list-disc space-y-1 pl-4">
                  {report.suggestions.map((s, i) => (
                    <li
                      key={i}
                      className="text-[11.5px] leading-relaxed text-neutral-600 dark:text-neutral-400"
                    >
                      {s}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
        {report && report.total_score < 8 ? (
          <div className="mb-2 flex items-start gap-1.5 text-[10.5px] leading-relaxed text-amber-600 dark:text-amber-400">
            <AlertTriangle className="mt-px h-3 w-3 shrink-0" />
            分数偏低，建议先修掉上面标红的问题，再重新检测一次。
          </div>
        ) : null}
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          disabled={checking}
          onClick={() => void handleCheck()}
        >
          {checking ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              评分中…
            </>
          ) : (
            "重新检测"
          )}
        </Button>
      </div>
    </div>
  );
}
