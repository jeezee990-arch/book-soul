/**
 * 写作页（主战场）：章节树 + 纸感编辑区 + 上下文面板。
 *
 * 2026-10 UI 重设计：
 * - 旧「创作」页 = 作品下拉 + 章节列表 + 编辑器，质检是另一个独立页面
 * - 现在所有章节级操作收进右栏 6 个 Tab（生成/重写/质检/人物/大纲/版本）
 * - 作品切换提到顶栏全局状态，这里只读不选
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, PenLine, Sparkles } from "lucide-react";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import type { Chapter, ChapterVersion, Novel } from "@/lib/types";
import type { NovelEditorHandle, NovelEditorSelection } from "@/components/NovelEditor";
import ChapterTree from "./chapter-tree";
import EditorPane from "./editor-pane";
import ContextPanel from "./context-panel";
import CreateChapterDialog from "@/components/create-chapter-dialog";
import { useChapterStream } from "./use-chapter-stream";
import type { PanelTab } from "./types";

export default function Writing() {
  const navigate = useNavigate();

  const novels = useNovelsStore((s) => s.novels);
  const loadNovels = useNovelsStore((s) => s.load);
  const novelId = useWorkspaceStore((s) => s.novelId);
  const chapterId = useWorkspaceStore((s) => s.chapterId);
  const setChapterId = useWorkspaceStore((s) => s.setChapterId);
  const setNovelId = useWorkspaceStore((s) => s.setNovelId);

  const novel: Novel | null = novels.find((n) => n.id === novelId) ?? null;

  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [editorContent, setEditorContent] = useState("");
  const [loadingEditor, setLoadingEditor] = useState(false);
  const [selection, setSelection] = useState<NovelEditorSelection | null>(null);
  const [panelTab, setPanelTab] = useState<PanelTab>("generate");
  const [versionTick, setVersionTick] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const editorRef = useRef<NovelEditorHandle>(null);

  const selectedChapter = chapters.find((c) => c.id === chapterId) ?? null;

  useEffect(() => {
    void loadNovels();
  }, [loadNovels]);

  // 拉章节
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
        if (cancelled) return;
        setChapters(data);
        // 保持当前章节；没有就默认选第一个
        const st = useWorkspaceStore.getState();
        const keep =
          st.chapterId !== null && data.some((c) => c.id === st.chapterId);
        const next = keep ? st.chapterId : (data[0]?.id ?? null);
        const ch = data.find((c) => c.id === next);
        setChapterId(
          next,
          ch ? `第 ${ch.chapter_number} 章${ch.title ? ` · ${ch.title}` : ""}` : null,
        );
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoadingChapters(false);
      });
    return () => {
      cancelled = true;
    };
  }, [novelId, setChapterId]);

  // 加载章节正文（最新版本）
  useEffect(() => {
    if (!selectedChapter) {
      setEditorContent("");
      return;
    }
    if (selectedChapter.current_version_id === null) {
      setEditorContent("");
      return;
    }
    let cancelled = false;
    setLoadingEditor(true);
    chaptersApi
      .getVersion(selectedChapter.id, selectedChapter.current_version_id)
      .then((v) => {
        if (!cancelled) setEditorContent(v.content || "");
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoadingEditor(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedChapter?.id, selectedChapter?.current_version_id]);

  /** 保存成功后：更新章节字数 / 版本号，并刷新右栏 */
  const handleSaved = useCallback(
    (version: ChapterVersion) => {
      setChapters((prev) =>
        prev.map((c) =>
          c.id === version.chapter_id
            ? {
                ...c,
                current_version_id: version.id,
                word_count: version.word_count,
              }
            : c,
        ),
      );
      setVersionTick((t) => t + 1);
    },
    [],
  );

  const stream = useChapterStream({
    chapter: selectedChapter,
    editorRef,
    onSaved: handleSaved,
  });

  /** 选章节：停掉正在跑的流 + 记住章节（持久化，下次打开回到这里） */
  const handleSelectChapter = useCallback(
    (id: number) => {
      stream.stop();
      const c = chapters.find((x) => x.id === id);
      setChapterId(
        id,
        c ? `第 ${c.chapter_number} 章${c.title ? ` · ${c.title}` : ""}` : null,
      );
    },
    [chapters, setChapterId, stream],
  );

  /** 质检 → 重写：切到重写 Tab */
  const handleRewriteFromQuality = useCallback((suggestion: string) => {
    setPanelTab("rewrite");
    // 把问题描述带到重写 Tab 的输入框（通过自定义事件）
    window.dispatchEvent(
      new CustomEvent("book-soul:rewrite-hint", { detail: suggestion }),
    );
  }, []);

  // ===== 空态（没选作品）=====
  if (novelId === null || !novel) {
    return (
      <EmptyWorkspace
        onNewBook={() => navigate("/new")}
        onOpenLibrary={() => navigate("/library")}
        onPickNovel={setNovelId}
        novels={novels}
      />
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <ChapterTree
        chapters={chapters}
        selectedId={chapterId}
        onSelect={handleSelectChapter}
        onCreate={() => setCreateOpen(true)}
        loading={loadingChapters}
      />

      <EditorPane
        ref={editorRef}
        chapter={selectedChapter}
        content={editorContent}
        onContentChange={() => {
          // 静默：手动保存走 saveContent，避免高频重渲染
        }}
        onSelection={setSelection}
        editable={!stream.generating && !stream.rewriting}
        loading={loadingEditor}
        savedVersionId={selectedChapter?.current_version_id ?? null}
        onOpenTab={setPanelTab}
        hasSelection={selection !== null}
      />

      <ContextPanel
        tab={panelTab}
        onTabChange={setPanelTab}
        novel={novel}
        chapter={selectedChapter}
        stream={stream}
        selection={selection}
        versionTick={versionTick}
        onRewriteFromQuality={handleRewriteFromQuality}
      />

      <CreateChapterDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        novelId={novel.id}
        existing={chapters}
        onCreated={(ch) => {
          setChapters((prev) =>
            [...prev, ch].sort((a, b) => a.chapter_number - b.chapter_number),
          );
          handleSelectChapter(ch.id);
        }}
      />

      {error ? (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[11.5px] text-rose-400">
          {error}
        </div>
      ) : null}
    </div>
  );
}

// ===== 空态 =====

function EmptyWorkspace({
  onNewBook,
  onOpenLibrary,
  onPickNovel,
  novels,
}: {
  onNewBook: () => void;
  onOpenLibrary: () => void;
  onPickNovel: (id: number) => void;
  novels: Novel[];
}) {
  const recent = novels.slice(0, 3);
  return (
    <div className="flex h-full items-center justify-center overflow-auto bg-neutral-50 dark:bg-neutral-950">
      <div className="w-[790px] max-w-[92%] py-10 text-center">
        <h2 className="text-[23px] font-semibold tracking-tight">今天想写点什么？</h2>
        <p className="mx-auto mt-2.5 max-w-[420px] text-[13px] leading-relaxed text-neutral-400">
          选一本旧书继续写，或者开一本新的。系统会记住你上次停在哪一章。
        </p>

        <div className="mt-8 grid grid-cols-3 gap-3">
          <button
            type="button"
            onClick={onNewBook}
            className="rounded-xl border border-neutral-200 bg-white p-4 text-left transition-colors hover:border-indigo-500/50 hover:-translate-y-px dark:border-neutral-800 dark:bg-neutral-900"
          >
            <span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-indigo-500/15 text-indigo-500">
              <Sparkles className="h-4 w-4" />
            </span>
            <h5 className="text-[13.5px] font-semibold">开一本新书</h5>
            <p className="mt-1 text-[11.5px] leading-relaxed text-neutral-400">
              题材 → 剧情 → 大纲 → 人物卡，三步生成可直接开写的作品骨架
            </p>
          </button>
          <button
            type="button"
            onClick={onOpenLibrary}
            className="rounded-xl border border-neutral-200 bg-white p-4 text-left transition-colors hover:border-indigo-500/50 hover:-translate-y-px dark:border-neutral-800 dark:bg-neutral-900"
          >
            <span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-violet-500/15 text-violet-500">
              <PenLine className="h-4 w-4" />
            </span>
            <h5 className="text-[13.5px] font-semibold">继续写</h5>
            <p className="mt-1 text-[11.5px] leading-relaxed text-neutral-400">
              回到上次的章节和光标位置，人物卡与上下文自动带出
            </p>
          </button>
          <button
            type="button"
            onClick={onOpenLibrary}
            className="rounded-xl border border-neutral-200 bg-white p-4 text-left transition-colors hover:border-indigo-500/50 hover:-translate-y-px dark:border-neutral-800 dark:bg-neutral-900"
          >
            <span className="mb-3 grid h-8 w-8 place-items-center rounded-lg bg-sky-500/15 text-sky-500">
              <BookOpen className="h-4 w-4" />
            </span>
            <h5 className="text-[13.5px] font-semibold">导入本地小说</h5>
            <p className="mt-1 text-[11.5px] leading-relaxed text-neutral-400">
              扫描指定目录，识别小说文件并接入为可编辑作品
            </p>
          </button>
        </div>

        {recent.length > 0 ? (
          <div className="mt-9 text-left">
            <div className="mb-2.5 flex items-center justify-between">
              <h6 className="text-[11px] font-semibold tracking-[0.08em] text-neutral-400 uppercase">
                最近的作品
              </h6>
              <button
                type="button"
                onClick={onOpenLibrary}
                className="text-[11.5px] text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
              >
                全部作品 →
              </button>
            </div>
            <div className="flex gap-2.5">
              {recent.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => onPickNovel(n.id)}
                  className="flex-1 rounded-lg border border-neutral-200 bg-white p-3 text-left transition-colors hover:border-indigo-500/50 dark:border-neutral-800 dark:bg-neutral-900"
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className="h-7 w-7 shrink-0 rounded"
                      style={{
                        background: `linear-gradient(150deg,#${(n.id * 137) % 4096}, #${(n.id * 331) % 4096})`,
                      }}
                      aria-hidden
                    />
                    <div className="min-w-0">
                      <div className="truncate text-[12.5px] font-semibold">
                        {n.name}
                      </div>
                      <div className="mt-0.5 text-[10.5px] text-neutral-400">
                        {n.genre}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
