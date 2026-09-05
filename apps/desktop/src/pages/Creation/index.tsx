import { useEffect, useRef, useState } from "react";
import { History, Sparkles, Wand2, X } from "lucide-react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import { readNdjsonStream, isStreamDone, isStreamError } from "@/api/streams";
import type { Chapter, ChapterVersion, Novel } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import EmptyState from "@/components/layout/EmptyState";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import NovelEditor, {
  type NovelEditorHandle,
  type NovelEditorSelection,
} from "@/components/NovelEditor";
import PromptBox from "@/components/PromptBox";
import NovelSelector from "./NovelSelector";
import ChapterList from "./ChapterList";
import CreateChapterDialog from "./CreateChapterDialog";
import VersionPanel from "./VersionPanel";

/** 创作 —— 选作品 → 章节列表 → Tiptap 编辑器（Phase 4.2/4.3/4.4） */
export default function Creation() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<number | null>(null);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [versionOpen, setVersionOpen] = useState(false);

  // 编辑器内容（HTML）
  const [editorContent, setEditorContent] = useState<string>("");
  const [loadingEditor, setLoadingEditor] = useState(false);
  const [selection, setSelection] = useState<NovelEditorSelection | null>(null);
  const [generating, setGenerating] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [showPromptFor, setShowPromptFor] = useState<"generate" | "rewrite" | null>(null);

  const editorRef = useRef<NovelEditorHandle>(null);
  const abortRef = useRef<AbortController | null>(null);

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

  // 章节切换时加载最新版本内容
  useEffect(() => {
    if (selectedChapterId === null) {
      setEditorContent("");
      return;
    }
    const chapter = chapters.find((c) => c.id === selectedChapterId);
    if (!chapter) {
      setEditorContent("");
      return;
    }
    if (chapter.current_version_id === null) {
      setEditorContent("");
      return;
    }
    setLoadingEditor(true);
    chaptersApi
      .getVersion(chapter.id, chapter.current_version_id)
      .then((v) => setEditorContent(v.content || ""))
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        toast.error("加载章节内容失败", { description: msg });
      })
      .finally(() => setLoadingEditor(false));
  }, [selectedChapterId, chapters]);

  // 卸载时取消流
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const selectedChapter = chapters.find((c) => c.id === selectedChapterId);

  function handleChapterCreated(chapter: Chapter) {
    setChapters((prev) => [...prev, chapter].sort((a, b) => a.chapter_number - b.chapter_number));
    setSelectedChapterId(chapter.id);
  }

  function handleRollback(newVersion: ChapterVersion) {
    if (!selectedChapter) return;
    setChapters((prev) =>
      prev.map((c) =>
        c.id === selectedChapter.id
          ? { ...c, current_version_id: newVersion.id, word_count: newVersion.word_count }
          : c,
      ),
    );
    setEditorContent(newVersion.content || "");
    toast.success("已生成回滚版本", { description: `v${newVersion.id}` });
  }

  // ===== 流式生成 =====
  async function startGenerate(userPrompt: string) {
    if (!selectedChapter) return;
    if (generating || rewriting) return;
    setGenerating(true);
    setShowPromptFor(null);
    abortRef.current = new AbortController();

    let accumulated = "";
    try {
      for await (const ev of readNdjsonStream(
        `/chapters/${selectedChapter.id}/generate`,
        {
          method: "POST",
          body: {
            user_prompt: userPrompt || "",
            target_word_count: 4000,
          },
          signal: abortRef.current.signal,
        },
      )) {
        if (isStreamError(ev)) {
          toast.error("生成失败", { description: ev.error });
          break;
        }
        if (isStreamDone(ev)) {
          break;
        }
        accumulated += ev.text;
        editorRef.current?.appendText(ev.text);
      }
      // 写一条新版本
      const finalText = accumulated.trim();
      if (finalText) {
        await saveContent(finalText, "llm_generate", userPrompt);
        toast.success("生成完成", { description: `${finalText.length} 字` });
      } else {
        toast.warning("生成未产生内容");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg !== "The user aborted a request.") {
        toast.error("生成异常", { description: msg });
      }
    } finally {
      setGenerating(false);
      abortRef.current = null;
    }
  }

  // ===== 选区重写 =====
  async function startRewrite(userPrompt: string) {
    if (!selectedChapter || !selection) {
      toast.error("请先在编辑器中选中文本");
      return;
    }
    if (generating || rewriting) return;
    setRewriting(true);
    setShowPromptFor(null);
    abortRef.current = new AbortController();

    const { from, to, text: originalText } = selection;
    let accumulated = "";
    try {
      for await (const ev of readNdjsonStream(
        `/chapters/${selectedChapter.id}/rewrite`,
        {
          method: "POST",
          body: {
            original_text: originalText,
            user_prompt: userPrompt,
            from_pos: from,
            to_pos: to,
          },
          signal: abortRef.current.signal,
        },
      )) {
        if (isStreamError(ev)) {
          toast.error("重写失败", { description: ev.error });
          break;
        }
        if (isStreamDone(ev)) {
          break;
        }
        accumulated += ev.text;
        // 用增量方式：每次 yield 后用整个 accumulated 替换选区
        editorRef.current?.replaceRange(from, from + accumulated.length, accumulated);
      }
      const finalText = accumulated.trim();
      if (finalText) {
        await saveContent(
          finalText,
          "rewrite",
          userPrompt,
          { from, to, original_length: originalText.length },
        );
        toast.success("重写完成", { description: `替换 ${originalText.length} → ${finalText.length} 字` });
      } else {
        toast.warning("重写未产生内容");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg !== "The user aborted a request.") {
        toast.error("重写异常", { description: msg });
      }
    } finally {
      setRewriting(false);
      abortRef.current = null;
    }
  }

  async function saveContent(
    content: string,
    trigger: string,
    prompt?: string,
    metadata?: Record<string, unknown>,
  ) {
    if (!selectedChapter) return;
    try {
      const version = await chaptersApi.saveContent(selectedChapter.id, {
        content,
        trigger,
        prompt: prompt || undefined,
        metadata,
      });
      // 刷新 chapter 状态
      setChapters((prev) =>
        prev.map((c) =>
          c.id === selectedChapter.id
            ? { ...c, current_version_id: version.id, word_count: version.word_count }
            : c,
        ),
      );
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("保存版本失败", { description: msg });
    }
  }

  function stopStream() {
    abortRef.current?.abort();
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

      {loadingChapters && <LoadingSkeleton rows={3} height={64} />}

      {!loadingChapters && novelId !== null && (
        <div className="grid grid-cols-[280px_1fr] gap-4">
          <ChapterList
            chapters={chapters}
            selectedId={selectedChapterId}
            onSelect={(id) => {
              stopStream();
              setSelectedChapterId(id);
            }}
            onCreate={() => setCreateOpen(true)}
            loading={loadingChapters}
          />

          <div className="space-y-3">
            {selectedChapter ? (
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1.5">
                      <CardTitle className="text-base">
                        第 {selectedChapter.chapter_number} 章 ·{" "}
                        {selectedChapter.title ?? "（未命名）"}
                      </CardTitle>
                      {selectedChapter.outline && (
                        <CardDescription>{selectedChapter.outline}</CardDescription>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setVersionOpen(true)}
                      className="shrink-0"
                    >
                      <History className="mr-1.5 h-3.5 w-3.5" />
                      版本历史
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Tiptap 编辑器 */}
                  <div className="rounded-md border border-neutral-200 dark:border-neutral-800 overflow-hidden bg-white dark:bg-neutral-950">
                    {loadingEditor ? (
                      <LoadingSkeleton rows={10} height={20} />
                    ) : (
                      <NovelEditor
                        ref={editorRef}
                        content={editorContent}
                        onChange={() => {
                          // 静默 onChange（避免高频重渲染）；手动保存走 saveContent
                        }}
                        onSelection={setSelection}
                        editable={!generating && !rewriting}
                      />
                    )}
                  </div>

                  {/* 操作栏 */}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        if (generating || rewriting) {
                          stopStream();
                          return;
                        }
                        setShowPromptFor("generate");
                      }}
                      disabled={rewriting}
                    >
                      <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                      {generating ? "停止生成" : "流式生成"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (rewriting) {
                          stopStream();
                          return;
                        }
                        if (!selection) {
                          toast.error("请先在编辑器中选中要重写的文本");
                          return;
                        }
                        setShowPromptFor("rewrite");
                      }}
                      disabled={generating || !selection}
                    >
                      <Wand2 className="mr-1.5 h-3.5 w-3.5" />
                      {rewriting ? "停止重写" : "选段重写"}
                    </Button>
                    {selection && (
                      <span className="text-[10px] text-neutral-500">
                        已选 {selection.text.length} 字
                      </span>
                    )}
                    {(generating || rewriting) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={stopStream}
                        className="ml-auto"
                      >
                        <X className="mr-1 h-3 w-3" />
                        取消
                      </Button>
                    )}
                    <span className="ml-auto text-[10px] text-neutral-400">
                      当前字数：{selectedChapter.word_count.toLocaleString()}
                    </span>
                  </div>

                  {/* Prompt 输入框（按需显示） */}
                  {showPromptFor && !generating && !rewriting && (
                    <div className="mt-3">
                      {showPromptFor === "generate" ? (
                        <PromptBox
                          action="generate"
                          onSubmit={startGenerate}
                          onClear={() => setShowPromptFor(null)}
                        />
                      ) : (
                        <PromptBox
                          action="rewrite"
                          onSubmit={startRewrite}
                          onClear={() => setShowPromptFor(null)}
                        />
                      )}
                    </div>
                  )}
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

      <VersionPanel
        open={versionOpen}
        onOpenChange={setVersionOpen}
        chapter={selectedChapter ?? null}
        onRollback={handleRollback}
      />
    </section>
  );
}
