import { useEffect, useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Novel, Chapter } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import EmptyState from "@/components/layout/EmptyState";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";

/** 创作 —— 选作品 → 章节列表 → 编辑器（Phase 3.9：Tiptap 占位） */
export default function Creation() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(
    null,
  );
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载作品列表
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
        if (!cancelled) {
          setError(msg);
          toast.error("拉取作品失败", { description: msg });
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingNovels(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 选定作品后加载章节
  useEffect(() => {
    if (novelId === null) return;
    let cancelled = false;
    setLoadingChapters(true);
    chaptersApi
      .list(novelId)
      .then((data) => {
        if (!cancelled) {
          setChapters(data);
          if (data.length > 0) setSelectedChapterId(data[0].id);
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

  const selectedChapter = chapters.find((c) => c.id === selectedChapterId);

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">创作</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          章节编辑与生成 · 人物卡一致 · 上下文记忆。
        </p>
      </header>

      {error && <ErrorState message={error} />}

      {!error && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-500">作品：</span>
          <Select
            value={novelId ? String(novelId) : undefined}
            onValueChange={(v) => setNovelId(Number(v))}
            disabled={loadingNovels || novels.length === 0}
          >
            <SelectTrigger className="w-64">
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
      )}

      {/* 加载中 */}
      {loadingChapters && <LoadingSkeleton rows={3} height={64} />}

      {/* 章节列表 + 编辑器 */}
      {!loadingChapters && chapters.length > 0 && (
        <div className="grid grid-cols-[260px_1fr] gap-4">
          {/* 左：章节列表 */}
          <div className="space-y-1.5 max-h-[600px] overflow-y-auto">
            {chapters.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedChapterId(c.id)}
                className={[
                  "w-full text-left rounded-md border px-3 py-2 text-sm transition-colors",
                  c.id === selectedChapterId
                    ? "border-neutral-900 dark:border-neutral-100 bg-neutral-50 dark:bg-neutral-900"
                    : "border-neutral-200 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-900/50",
                ].join(" ")}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    第 {c.chapter_number} 章 · {c.title ?? "（未命名）"}
                  </span>
                  <span className="text-[10px] text-neutral-400">
                    {c.status}
                  </span>
                </div>
                <div className="mt-0.5 text-[10px] text-neutral-500">
                  {c.word_count.toLocaleString()} 字
                </div>
              </button>
            ))}
          </div>

          {/* 右：Tiptap 编辑器占位 */}
          <div className="space-y-3">
            {selectedChapter ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    第 {selectedChapter.chapter_number} 章 ·{" "}
                    {selectedChapter.title ?? "（未命名）"}
                  </CardTitle>
                  {selectedChapter.outline && (
                    <CardDescription>{selectedChapter.outline}</CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  {/* MOCK: Tiptap 编辑器占位（Phase 4.2 真实接入 Tiptap） */}
                  <div className="rounded-md border border-dashed border-neutral-300 dark:border-neutral-700 p-6 bg-neutral-50/50 dark:bg-neutral-900/30">
                    <p className="text-xs text-neutral-500 text-center">
                      Tiptap 编辑器占位（Phase 4.2 接入）
                    </p>
                    <Textarea
                      placeholder="在此处输入或流式生成章节内容……"
                      className="mt-3 min-h-[300px] font-mono text-sm"
                      disabled
                    />
                    <div className="mt-3 flex items-center gap-2">
                      <Button size="sm" disabled title="Phase 4.2 接入">
                        流式生成
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled
                        title="Phase 4.2 接入"
                      >
                        选段重写
                      </Button>
                      <span className="ml-auto text-[10px] text-neutral-400">
                        字数：0
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <EmptyState
                icon="📝"
                title="选一章节开始编辑"
                description="左边点章节，或新建一个。"
              />
            )}
          </div>
        </div>
      )}

      {/* 无章节空状态 */}
      {!loadingChapters && novelId !== null && chapters.length === 0 && (
        <EmptyState
          icon="📖"
          title="该作品暂无章节"
          description="Phase 4 接入章节生成后，这里会出现自动生成的章节列表。"
        />
      )}
    </section>
  );
}
