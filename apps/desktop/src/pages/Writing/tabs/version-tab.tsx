/**
 * 版本 Tab：版本树 + diff 对比 + 回滚。
 *
 * 逻辑沿用旧创作页的 VersionPanel（同一个 versionsApi），
 * 只是从弹窗改成右栏常驻，随时可对比随时可回滚。
 */

import { useCallback, useEffect, useState } from "react";
import { History, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { versionsApi, type DiffResponse } from "@/api/versions";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Chapter, ChapterVersion } from "@/lib/types";
import { HintBar, SectionLabel } from "../ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** 版本触发方式 → 中文标签。 */
const TRIGGER_LABEL: Record<string, string> = {
  llm_generate: "LLM 生成",
  rewrite: "选段重写",
  manual: "手动保存",
  manual_edit: "手动编辑",
  rollback: "回滚",
  create: "新建",
};

interface Props {
  chapter: Chapter | null;
  /** 版本变化时刷新（生成完 / 回滚后） */
  versionTick: number;
  /** 回滚成功后通知父级更新正文 */
  onRolledBack?: (version: ChapterVersion) => void;
}

export default function VersionTab({
  chapter,
  versionTick,
  onRolledBack,
}: Props) {
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);

  const load = useCallback(async (chapterId: number) => {
    setLoading(true);
    try {
      const list = await chaptersApi.listVersions(chapterId);
      setVersions(list);
      // 默认选中当前版本
      setSelectedId((prev) => {
        if (prev !== null && list.some((v) => v.id === prev)) return prev;
        return list.length > 0 ? list[list.length - 1].id : null;
      });
    } catch (e: unknown) {
      toast.error("加载版本失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!chapter) {
      setVersions([]);
      setSelectedId(null);
      return;
    }
    void load(chapter.id);
  }, [chapter, load, versionTick]);

  // 选中版本 → 拉 diff
  useEffect(() => {
    if (!chapter || selectedId === null) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    setDiffLoading(true);
    versionsApi
      .diff(chapter.id, selectedId)
      .then((resp) => {
        if (!cancelled) setDiff(resp);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          toast.error("加载 diff 失败", {
            description: e instanceof ApiError ? e.message : String(e),
          });
        }
      })
      .finally(() => {
        if (!cancelled) setDiffLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chapter, selectedId]);

  async function handleRollback() {
    if (!chapter || selectedId === null) return;
    if (
      !confirm(
        "确认回滚到该版本？将生成一条新版本（parent = 当前最新），原历史保留。",
      )
    )
      return;
    setRollingBack(true);
    try {
      const resp = await versionsApi.rollback(chapter.id, selectedId);
      toast.success("已回滚", { description: `新建版本 #${resp.new_version.id}` });
      onRolledBack?.(resp.new_version);
      await load(chapter.id);
    } catch (e: unknown) {
      toast.error("回滚失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setRollingBack(false);
    }
  }

  if (!chapter) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        先在左边选一个章节
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="min-h-0 flex-1 px-3.5 py-3.5">
        <h4 className="text-[12.5px] font-semibold">版本历史</h4>
        <p className="mt-0.5 mb-3 text-[11.5px] leading-relaxed text-neutral-400">
          每次生成 / 重写 / 手动保存都会存一版，可对比、可回滚。
        </p>

        {loading && versions.length === 0 ? (
          <div className="space-y-1.5">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800/60"
              />
            ))}
          </div>
        ) : null}

        {!loading && versions.length === 0 ? (
          <div className="py-8 text-center">
            <History className="mx-auto mb-2 h-6 w-6 text-neutral-300 dark:text-neutral-700" />
            <p className="text-[12px] text-neutral-400">还没有版本</p>
          </div>
        ) : null}

        {versions.length > 0 ? (
          <div className="relative mb-3 space-y-1 pl-4">
            {/* 版本树竖线 */}
            <span
              className="absolute top-2 bottom-2 left-[5px] w-px bg-neutral-200 dark:bg-neutral-800"
              aria-hidden
            />
            {versions.map((v) => {
              const on = v.id === selectedId;
              const isCurrent = v.id === chapter.current_version_id;
              return (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setSelectedId(v.id)}
                  className={cn(
                    "relative block w-full rounded-lg border px-2.5 py-1.5 text-left transition-colors",
                    on
                      ? "border-indigo-500/50 bg-indigo-500/10"
                      : "border-transparent hover:bg-neutral-100 dark:hover:bg-neutral-800",
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-2.5 -left-[13px] h-2 w-2 rounded-full border-2 border-white dark:border-neutral-900",
                      isCurrent
                        ? "bg-emerald-500"
                        : on
                          ? "bg-indigo-500"
                          : "bg-neutral-300 dark:bg-neutral-700",
                    )}
                    aria-hidden
                  />
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-[11px] text-neutral-500 dark:text-neutral-400">
                      v{v.id}
                    </span>
                    <span className="text-[11px] text-neutral-400">
                      {TRIGGER_LABEL[v.trigger] ?? v.trigger}
                    </span>
                    {isCurrent ? (
                      <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9.5px] text-emerald-600 dark:text-emerald-400">
                        当前
                      </span>
                    ) : null}
                    <span className="ml-auto font-mono text-[10px] text-neutral-400">
                      {v.word_count.toLocaleString()}
                    </span>
                  </span>
                  {v.prompt ? (
                    <span className="mt-0.5 block truncate text-[10.5px] text-neutral-400">
                      {v.prompt}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        ) : null}

        {diffLoading ? (
          <div className="flex items-center gap-2 px-1 py-3 text-[11.5px] text-neutral-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            加载差异…
          </div>
        ) : null}

        {diff && !diffLoading ? (
          <>
            <SectionLabel
              action={
                <span className="font-mono text-[10px] text-neutral-400">
                  +{diff.stats.added} / -{diff.stats.removed}
                </span>
              }
            >
              差异
            </SectionLabel>
            <div className="max-h-[220px] overflow-auto rounded-lg border border-neutral-200 font-mono text-[10.5px] leading-relaxed dark:border-neutral-800">
              {diff.diff
                .split("\n")
                .slice(0, 200)
                .map((line, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex gap-1.5 px-2 py-px",
                      line.startsWith("+") &&
                        !line.startsWith("+++") &&
                        "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
                      line.startsWith("-") &&
                        !line.startsWith("---") &&
                        "bg-rose-500/10 text-rose-500/80",
                      !line.startsWith("+") &&
                        !line.startsWith("-") &&
                        "text-neutral-500 dark:text-neutral-400",
                    )}
                  >
                    <span className="w-2 shrink-0 opacity-60">
                      {line.startsWith("+") ? "+" : line.startsWith("-") ? "-" : " "}
                    </span>
                    <span className="min-w-0 flex-1 break-all">{line}</span>
                  </div>
                ))}
            </div>
          </>
        ) : null}

        {versions.length > 0 && diff && diff.stats.added === 0 && diff.stats.removed === 0 ? (
          <div className="mt-2">
            <HintBar>这个版本与前一个没有差异。</HintBar>
          </div>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-neutral-200 p-3 dark:border-neutral-800">
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          disabled={rollingBack || selectedId === null || selectedId === chapter.current_version_id}
          onClick={() => void handleRollback()}
        >
          {rollingBack ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
          ) : (
            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
          )}
          回滚到此版本
        </Button>
      </div>
    </div>
  );
}
