import { useEffect, useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Chapter, Novel } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import EmptyState from "@/components/layout/EmptyState";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import NovelSelector from "./NovelSelector";
import ChapterList from "./ChapterList";
import CreateChapterDialog from "./CreateChapterDialog";

/** 创作 —— 选作品 → 章节列表 → 编辑器（Phase 4.1：组件化 + 新建章节） */
export default function Creation() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

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
    if (novelId === null) {
      setChapters([]);
      setSelectedChapterId(null);
      return;
    }
    let cancelled = false;
    setLoadingChapters(true);
    chaptersApi
      .list(novelId)
      .then((data) => {
        if (!cancelled) {
          setChapters(data);
          setSelectedChapterId(data.length > 0 ? data[0].id : null);
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

  function handleChapterCreated(chapter: Chapter) {
    setChapters((prev) => [...prev, chapter].sort((a, b) => a.chapter_number - b.chapter_number));
    setSelectedChapterId(chapter.id);
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">创作</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          章节编辑与生成 · 人物卡一致 · 上下文记忆。
        </p>
      </header>

      {error && <ErrorState message={error} />}

      {!error && novels.length > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-500">作品：</span>
          <NovelSelector
            novels={novels}
            value={novelId}
            onChange={setNovelId}
            loading={loadingNovels}
          />
        </div>
      )}

      {/* 加载中 */}
      {loadingChapters && <LoadingSkeleton rows={3} height={64} />}

      {/* 章节列表 + 编辑器 */}
      {!loadingChapters && novelId !== null && (
        <div className="grid grid-cols-[280px_1fr] gap-4">
          <ChapterList
            chapters={chapters}
            selectedId={selectedChapterId}
            onSelect={setSelectedChapterId}
            onCreate={() => setCreateOpen(true)}
            loading={loadingChapters}
          />

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
                      <Button size="sm" disabled title="Phase 4.3 接入">
                        流式生成
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled
                        title="Phase 4.4 接入"
                      >
                        选段重写
                      </Button>
                      <span className="ml-auto text-[10px] text-neutral-400">
                        当前字数：{selectedChapter.word_count.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <EmptyState
                icon="📝"
                title="选一章节开始编辑"
                description="左边点章节，或点「新建章节」开始。"
              />
            )}
          </div>
        </div>
      )}

      <CreateChapterDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        novelId={novelId}
        existing={chapters}
        onCreated={handleChapterCreated}
      />
    </section>
  );
}
