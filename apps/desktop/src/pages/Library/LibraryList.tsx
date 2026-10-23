/**
 * 作品卡片网格（素材库 · 作品 Tab）。
 *
 * 2026-10 UI 重设计：旧「作品库」有「作品」和「藏书馆」两个 Tab，
 * 唯一区别是"有没有章节"—— 对作者来说是同一个概念列表。
 * 现在合并为一份，用状态标签区分，藏书馆语义取消。
 *
 * 字数 / 章数是后端 Novel 模型里没有的字段，这里异步补齐
 *（逐本拉章节列表汇总），不阻塞首屏渲染。
 */

import { useEffect, useState } from "react";
import { BookOpen, FileDown, PenLine } from "lucide-react";
import { toast } from "sonner";
import { novelsApi, downloadExportFile } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  onSelect: (novel: Novel) => void;
  /** 继续写：切到写作页并选中该作品 */
  onContinue: (novel: Novel) => void;
}

/** 作品的章节统计（异步补齐）。 */
interface Stat {
  words: number;
  chapters: number;
  written: number;
}

const EMPTY_STAT: Stat = { words: 0, chapters: 0, written: 0 };

/** 状态 → 圆点颜色 + 中文 */
function statusMeta(novel: Novel): { dot: string; label: string } {
  if (novel.imported) return { dot: "bg-neutral-400", label: "已导入" };
  switch (novel.status) {
    case "draft":
      return { dot: "bg-neutral-400", label: "草稿" };
    case "writing":
    case "serializing":
      return { dot: "bg-violet-500", label: "连载中" };
    case "done":
    case "finished":
      return { dot: "bg-emerald-500", label: "已完成" };
    default:
      return { dot: "bg-indigo-500", label: novel.status || "进行中" };
  }
}

export default function LibraryList({ onSelect, onContinue }: Props) {
  const [items, setItems] = useState<Novel[]>([]);
  const [stats, setStats] = useState<Record<number, Stat>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "writing" | "draft" | "imported">(
    "all",
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    novelsApi
      .list()
      .then((data) => {
        if (cancelled) return;
        setItems(data);
        setLoading(false);

        // 后台补齐章节统计（不阻塞首屏）
        void Promise.all(
          data.map(async (n) => {
            try {
              const chs = await chaptersApi.list(n.id);
              const stat: Stat = {
                words: chs.reduce((sum, c) => sum + c.word_count, 0),
                chapters: chs.length,
                written: chs.filter((c) => c.word_count > 0).length,
              };
              if (!cancelled) setStats((prev) => ({ ...prev, [n.id]: stat }));
            } catch {
              // 单本失败忽略
            }
          }),
        );
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setError(msg);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExport(novel: Novel, format: "md" | "html" | "docx") {
    try {
      const file = await novelsApi.export(novel.id, format);
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    }
  }

  const filtered = items.filter((n) => {
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      if (
        !n.name.toLowerCase().includes(q) &&
        !n.genre.toLowerCase().includes(q)
      ) {
        return false;
      }
    }
    if (filter === "imported") return n.imported;
    if (filter === "draft") return !n.imported && n.status === "draft";
    if (filter === "writing") return !n.imported && n.status !== "draft";
    return true;
  });

  return (
    <div>
      {/* 搜索 + 筛选 */}
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <div className="relative w-[280px]">
          <svg
            viewBox="0 0 24 24"
            className="absolute top-2 left-2.5 h-[15px] w-[15px] text-neutral-400"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4-4" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索作品名、题材…"
            className="h-8 w-full rounded-lg border border-neutral-200 bg-white pr-2.5 pl-8.5 text-[12.5px] outline-none focus:border-indigo-500/50 dark:border-neutral-800 dark:bg-neutral-900"
            style={{ paddingLeft: "2.1rem" }}
          />
        </div>
        <div className="flex gap-0.5 rounded-lg border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-800/40">
          {(
            [
              { v: "all", t: "全部" },
              { v: "writing", t: "连载中" },
              { v: "draft", t: "草稿" },
              { v: "imported", t: "已导入" },
            ] as const
          ).map((o) => (
            <button
              key={o.v}
              type="button"
              onClick={() => setFilter(o.v)}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-[11.5px] transition-colors",
                filter === o.v
                  ? "bg-white font-medium shadow-sm dark:bg-neutral-700 dark:text-neutral-50"
                  : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200",
              )}
            >
              {o.t}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[11.5px] text-neutral-400">
          共 {filtered.length} 部
        </span>
      </div>

      {error ? (
        <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[12px] text-rose-500">
          加载失败：{error}
        </p>
      ) : null}

      {loading ? (
        <div className="grid grid-cols-4 gap-3">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div
              key={i}
              className="h-[186px] animate-pulse rounded-xl bg-neutral-100 dark:bg-neutral-800/60"
            />
          ))}
        </div>
      ) : null}

      {!loading && filtered.length === 0 ? (
        <div className="py-16 text-center">
          <BookOpen className="mx-auto mb-2.5 h-7 w-7 text-neutral-300 dark:text-neutral-700" />
          <p className="text-[13px] text-neutral-400">还没有作品</p>
          <p className="mt-1 text-[11.5px] text-neutral-400">
            去「开新书」走一遍三步流程，或从「导入」接入本地小说
          </p>
        </div>
      ) : null}

      {!loading && filtered.length > 0 ? (
        <div className="grid grid-cols-4 gap-3">
          {filtered.map((n) => {
            const meta = statusMeta(n);
            const stat = stats[n.id] ?? EMPTY_STAT;
            const progress = stat.chapters
              ? Math.round((stat.written / stat.chapters) * 100)
              : 0;
            return (
              <div
                key={n.id}
                className="group relative overflow-hidden rounded-xl border border-neutral-200 bg-white transition-all hover:-translate-y-px hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700"
              >
                <button
                  type="button"
                  onClick={() => onSelect(n)}
                  className="block w-full text-left"
                >
                  <div
                    className="grid h-[98px] place-items-center"
                    style={{
                      background: `linear-gradient(150deg, hsl(${(n.id * 47) % 360} 32% 26%), hsl(${(n.id * 83) % 360} 38% 17%))`,
                    }}
                  >
                    {/* 封面用书名首字：跨平台渲染一致，也不像 emoji 那样抢视觉 */}
                    <span className="text-[36px] font-semibold tracking-tight text-white/85">
                      {(n.name || "书").trim().charAt(0)}
                    </span>
                  </div>
                  <div className="p-3">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={cn("h-1.5 w-1.5 rounded-full", meta.dot)}
                      />
                      <span className="truncate text-[13px] font-semibold">
                        {n.name}
                      </span>
                    </div>
                    <div className="mt-1.5 flex gap-2 text-[11px] text-neutral-400">
                      <span>{n.genre}</span>
                      <span className="font-mono">
                        {stat.words.toLocaleString()} 字
                      </span>
                      <span>
                        {stat.written}/{stat.chapters} 章
                      </span>
                    </div>
                    <div className="mt-2.5 h-[3px] overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
                      <i
                        className="block h-full rounded-full bg-indigo-500"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                </button>

                {/* 悬停操作 */}
                <div className="absolute top-2.5 right-2.5 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                  <button
                    type="button"
                    onClick={() => onContinue(n)}
                    title="继续写"
                    className="inline-flex h-6 items-center gap-1 rounded-md bg-white/90 px-2 text-[10.5px] text-neutral-700 shadow-sm backdrop-blur hover:bg-white dark:bg-neutral-800/90 dark:text-neutral-200"
                  >
                    <PenLine className="h-3 w-3" />
                    继续写
                  </button>
                </div>

                <div className="flex items-center gap-0.5 border-t border-neutral-200/70 px-2 py-1 dark:border-neutral-800/70">
                  {(["md", "html", "docx"] as const).map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() => void handleExport(n, fmt)}
                      className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[10px] text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
                    >
                      <FileDown className="h-2.5 w-2.5" />
                      {fmt === "docx" ? "Word" : fmt.toUpperCase()}
                    </button>
                  ))}
                  <span className="ml-auto text-[10px] text-neutral-400">
                    {meta.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
