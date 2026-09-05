import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Loader2, Sparkles, ChevronDown } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import EmptyState from "@/components/layout/EmptyState";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import { novelsApi } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { qualityApi, type QualityReport } from "@/api/quality";
import { ApiError } from "@/api";
import type { Chapter, Novel } from "@/lib/types";
import { cn } from "@/lib/utils";

const DIMENSION_LABELS: Record<string, string> = {
  writing: "文笔",
  logic: "逻辑",
  pacing: "节奏",
  consistency: "一致性",
  genre: "题材合规",
};

function scoreTone(score: number): string {
  if (score >= 8) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 6) return "text-amber-600 dark:text-amber-400";
  return "text-rose-600 dark:text-rose-400";
}

/** 质检页（Phase 5.1 + 5.5）：
 * - 选作品 / 选章节
 * - 触发 5 维度并行评分（~10-30s）
 * - 总分 + recharts 雷达图
 * - 维度详情：issues + suggestions
 */
export default function QualityCheck() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapterId, setChapterId] = useState<number | null>(null);
  const [report, setReport] = useState<QualityReport | null>(null);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  // 加载作品
  useEffect(() => {
    let cancelled = false;
    setLoadingNovels(true);
    setError(null);
    novelsApi
      .list()
      .then((data) => {
        if (!cancelled) {
          setNovels(data);
          if (data.length > 0) setNovelId(data[0].id);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoadingNovels(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 加载章节
  useEffect(() => {
    if (novelId === null) {
      setChapters([]);
      setChapterId(null);
      return;
    }
    let cancelled = false;
    setLoadingChapters(true);
    chaptersApi
      .list(novelId)
      .then((data) => {
        if (!cancelled) {
          // 只显示有内容的章节
          const withContent = data.filter((c) => c.word_count > 0);
          setChapters(withContent);
          setChapterId(withContent[0]?.id ?? null);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) toast.error("拉取章节失败", { description: msg });
      })
      .finally(() => {
        if (!cancelled) setLoadingChapters(false);
      });
    return () => {
      cancelled = true;
    };
  }, [novelId]);

  async function handleCheck() {
    if (novelId === null || chapterId === null) return;
    setChecking(true);
    setReport(null);
    setExpandedDim(null);
    try {
      const r = await qualityApi.check(novelId, chapterId);
      setReport(r);
      toast.success("质检完成", { description: `总分 ${r.total_score} / 10` });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("质检失败", { description: msg });
    } finally {
      setChecking(false);
    }
  }

  const radarData = useMemo(() => {
    if (!report) return [];
    return Object.entries(report.dimension_scores).map(([k, v]) => ({
      dimension: DIMENSION_LABELS[k] ?? k,
      value: Math.round(v * 10), // 0-100
      fullMark: 100,
    }));
  }, [report]);

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">质检</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          5 维度并行评分（文笔 / 逻辑 / 节奏 / 一致性 / 题材合规）· 30s 内出报告。
        </p>
      </header>

      {error && <ErrorState message={error} />}

      {!error && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">运行质检</CardTitle>
            <CardDescription>
              选作品和章节（需有正文）→ 点「开始检测」→ 等 5 维度 LLM 评分
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm text-neutral-500">作品</span>
                <Select
                  value={novelId !== null ? String(novelId) : undefined}
                  onValueChange={(v) => setNovelId(Number(v))}
                  disabled={loadingNovels || novels.length === 0}
                >
                  <SelectTrigger className="w-56">
                    <SelectValue placeholder="选择作品" />
                  </SelectTrigger>
                  <SelectContent>
                    {novels.map((n) => (
                      <SelectItem key={n.id} value={String(n.id)}>
                        {n.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-neutral-500">章节</span>
                <Select
                  value={chapterId !== null ? String(chapterId) : undefined}
                  onValueChange={(v) => setChapterId(Number(v))}
                  disabled={loadingChapters || chapters.length === 0}
                >
                  <SelectTrigger className="w-72">
                    <SelectValue placeholder="选择章节" />
                  </SelectTrigger>
                  <SelectContent>
                    {chapters.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        第 {c.chapter_number} 章 · {c.title ?? "（未命名）"} ·{" "}
                        {c.word_count.toLocaleString()} 字
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={handleCheck}
                disabled={checking || chapterId === null}
              >
                {checking ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    评分中…
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    开始检测
                  </>
                )}
              </Button>
            </div>
            {chapters.length === 0 && novelId !== null && !loadingChapters && (
              <p className="text-xs text-neutral-500">
                该作品下没有有正文的章节（先去创作页生成）
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {checking && <LoadingSkeleton rows={6} height={80} />}

      {!checking && !report && !error && (
        <EmptyState
          icon="📊"
          title="还没有质检报告"
          description="选章节 → 点「开始检测」→ 等报告"
        />
      )}

      {report && (
        <div className="space-y-4">
          {/* 总分 + 雷达图 */}
          <div className="grid gap-4 md:grid-cols-[280px_1fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">综合评分</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "text-6xl font-bold tabular-nums",
                      scoreTone(report.total_score),
                    )}
                  >
                    {report.total_score.toFixed(1)}
                  </div>
                  <div className="text-xs text-neutral-500">/ 10</div>
                  <div className="mt-3 text-[10px] text-neutral-400 text-center">
                    {report.chapter_title}
                    <br />
                    题材 {report.genre} · {report.provider}/{report.model}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">5 维度雷达图</CardTitle>
              </CardHeader>
              <CardContent>
                <div style={{ width: "100%", height: 320 }}>
                  <ResponsiveContainer>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="currentColor" strokeOpacity={0.2} />
                      <PolarAngleAxis
                        dataKey="dimension"
                        tick={{ fill: "currentColor", fontSize: 12 }}
                      />
                      <PolarRadiusAxis
                        angle={90}
                        domain={[0, 100]}
                        tick={{ fontSize: 10 }}
                      />
                      <Radar
                        name="分数"
                        dataKey="value"
                        stroke="#6366f1"
                        fill="#6366f1"
                        fillOpacity={0.4}
                      />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload || payload.length === 0) return null;
                          const p = payload[0];
                          return (
                            <div className="rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 px-2 py-1 text-xs shadow">
                              <div className="font-medium">{p.payload.dimension}</div>
                              <div>{p.value} / 100</div>
                            </div>
                          );
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 5 维度详情（可展开） */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">维度详情</CardTitle>
              <CardDescription>
                点击展开每维度的问题和原文引用
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {report.dimension_results.map((r) => {
                const open = expandedDim === r.dimension;
                return (
                  <div
                    key={r.dimension}
                    className="rounded-md border border-neutral-200 dark:border-neutral-800 overflow-hidden"
                  >
                    <button
                      onClick={() => setExpandedDim(open ? null : r.dimension)}
                      className="w-full px-3 py-2 flex items-center justify-between hover:bg-neutral-50 dark:hover:bg-neutral-900/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {DIMENSION_LABELS[r.dimension] ?? r.dimension}
                        </span>
                        {r.error && (
                          <span className="text-[10px] text-rose-500">
                            评分失败
                          </span>
                        )}
                        <span className="text-[10px] text-neutral-400">
                          {r.issues.length} 个问题 · {r.suggestions.length} 条建议
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "text-lg font-semibold tabular-nums",
                            scoreTone(r.score),
                          )}
                        >
                          {r.score.toFixed(1)}
                        </span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 text-neutral-400 transition-transform",
                            open && "rotate-180",
                          )}
                        />
                      </div>
                    </button>
                    {open && (
                      <div className="px-3 py-2 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/30 space-y-2">
                        {r.error && (
                          <p className="text-xs text-rose-500">
                            错误：{r.error}
                          </p>
                        )}
                        {r.issues.length === 0 && !r.error && (
                          <p className="text-xs text-neutral-500">
                            没有明显问题 ✨
                          </p>
                        )}
                        {r.issues.map((issue, idx) => (
                          <div
                            key={idx}
                            className="rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-2 text-xs space-y-1"
                          >
                            <div className="flex items-center gap-1.5 text-[10px] text-neutral-500">
                              {issue.character && (
                                <span className="rounded bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 px-1 py-0.5">
                                  {issue.character}
                                </span>
                              )}
                              {issue.type && (
                                <span className="rounded bg-neutral-100 dark:bg-neutral-800 px-1 py-0.5">
                                  {issue.type}
                                </span>
                              )}
                            </div>
                            {issue.quote && (
                              <blockquote className="border-l-2 border-neutral-300 dark:border-neutral-700 pl-2 italic text-neutral-600 dark:text-neutral-400">
                                {issue.quote}
                              </blockquote>
                            )}
                            {issue.problem && (
                              <p>
                                <span className="text-rose-500">问题：</span>
                                {issue.problem}
                              </p>
                            )}
                            {issue.suggestion && (
                              <p>
                                <span className="text-emerald-500">建议：</span>
                                {issue.suggestion}
                              </p>
                            )}
                          </div>
                        ))}
                        {r.suggestions.length > 0 && (
                          <div className="pt-1">
                            <p className="text-[10px] font-medium text-neutral-500 mb-1">
                              整体建议
                            </p>
                            <ul className="text-xs text-neutral-600 dark:text-neutral-400 space-y-0.5 list-disc pl-4">
                              {r.suggestions.map((s, i) => (
                                <li key={i}>{s}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* 整体建议合并 */}
          {report.suggestions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">整体建议（合并）</CardTitle>
                <CardDescription>跨维度的改进建议</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-neutral-700 dark:text-neutral-300 space-y-1 list-disc pl-5">
                  {report.suggestions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}
