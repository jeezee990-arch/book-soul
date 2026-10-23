import { useEffect, useState } from "react";
import { History, FileDown, BookOpen, X, Eye } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { chaptersApi } from "@/api/chapters";
import { novelsApi, downloadExportFile } from "@/api/novels";
import { charactersApi } from "@/api/characters";
import { outlinesApi } from "@/api/outlines";
import { ApiError } from "@/api";
import type { Chapter, ChapterVersion, Character, Novel, Outline } from "@/lib/types";
import { cn } from "@/lib/utils";
import VersionPanel from "@/components/version-panel";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  novel: Novel | null;
}

/** 藏书详情 dialog（Phase 6.2）：
 * - 章节列表（可滚动）
 * - 章节只读查看（弹嵌套 dialog）
 * - 版本历史（复用 VersionPanel）
 * - 导出
 */
export default function LibraryDetail({ open, onOpenChange, novel }: Props) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [outline, setOutline] = useState<Outline | null>(null);
  const [loading, setLoading] = useState(false);

  // 章节查看
  const [viewChapter, setViewChapter] = useState<Chapter | null>(null);
  const [viewVersion, setViewVersion] = useState<ChapterVersion | null>(null);
  const [viewLoading, setViewLoading] = useState(false);

  // 版本历史
  const [versionChapter, setVersionChapter] = useState<Chapter | null>(null);

  useEffect(() => {
    if (!open || !novel) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      chaptersApi.list(novel.id),
      charactersApi.list(novel.id).catch(() => []),
      outlinesApi.list(novel.id).catch(() => []),
    ])
      .then(([chs, chars, outs]) => {
        if (cancelled) return;
        setChapters(chs);
        setCharacters(chars);
        setOutline(outs[0] ?? null);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        toast.error("加载作品详情失败", { description: msg });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, novel]);

  async function handleViewChapter(ch: Chapter) {
    if (!ch.current_version_id) {
      toast.warning("该章节暂无内容");
      return;
    }
    setViewChapter(ch);
    setViewLoading(true);
    try {
      const v = await chaptersApi.getVersion(ch.id, ch.current_version_id);
      setViewVersion(v);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("加载章节失败", { description: msg });
      setViewChapter(null);
    } finally {
      setViewLoading(false);
    }
  }

  async function handleExport(format: "md" | "html" | "docx") {
    if (!novel) return;
    try {
      const file = await novelsApi.export(novel.id, format);
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    }
  }

  if (!novel) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              {novel.name}
              <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5 ml-1">
                {novel.genre}
              </span>
            </DialogTitle>
            <DialogDescription>
              {novel.description || "（无简介）"}
            </DialogDescription>
          </DialogHeader>

          <Tabs defaultValue="chapters">
            <TabsList>
              <TabsTrigger value="chapters">章节（{chapters.length}）</TabsTrigger>
              <TabsTrigger value="characters">
                人物卡（{characters.length}）
              </TabsTrigger>
              <TabsTrigger value="outline">大纲</TabsTrigger>
            </TabsList>

            <TabsContent value="chapters" className="mt-3 space-y-1.5 max-h-[480px] overflow-auto">
              {loading ? (
                <p className="text-xs text-neutral-400">加载中…</p>
              ) : chapters.length === 0 ? (
                <p className="text-xs text-neutral-400">暂无章节</p>
              ) : (
                chapters.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between rounded-md border border-neutral-200 dark:border-neutral-800 px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900/30"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        第 {c.chapter_number} 章 · {c.title ?? "（未命名）"}
                      </span>
                      <span className="rounded bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 text-[10px]">
                        {c.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-neutral-500">
                        {c.word_count.toLocaleString()} 字
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2"
                        onClick={() => handleViewChapter(c)}
                        disabled={!c.current_version_id}
                      >
                        <Eye className="mr-1 h-3 w-3" />
                        查看
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2"
                        onClick={() => setVersionChapter(c)}
                      >
                        <History className="mr-1 h-3 w-3" />
                        版本
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="characters" className="mt-3 space-y-2 max-h-[480px] overflow-auto">
              {characters.length === 0 ? (
                <p className="text-xs text-neutral-400">暂无人物卡</p>
              ) : (
                characters.map((c) => (
                  <div
                    key={c.id}
                    className={cn(
                      "rounded-md border p-2 text-sm",
                      c.is_active
                        ? "border-neutral-200 dark:border-neutral-800"
                        : "border-neutral-100 dark:border-neutral-900 opacity-60",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      <span className="rounded bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 text-[10px]">
                        {c.role}
                      </span>
                      {!c.is_active && (
                        <span className="text-[10px] text-rose-500">退场</span>
                      )}
                    </div>
                    {c.personality && (
                      <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
                        {c.personality}
                      </p>
                    )}
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="outline" className="mt-3">
              {!outline ? (
                <p className="text-xs text-neutral-400">暂无大纲</p>
              ) : (
                <pre className="text-xs font-mono text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap rounded-md bg-neutral-50 dark:bg-neutral-900/50 p-3 max-h-[480px] overflow-auto">
                  {JSON.stringify(outline.structure, null, 2)}
                </pre>
              )}
            </TabsContent>
          </Tabs>

          {/* 操作栏 */}
          <div className="flex items-center gap-2 border-t border-neutral-200 dark:border-neutral-800 pt-3 mt-3">
            <span className="text-xs text-neutral-500">导出：</span>
            <Button size="sm" variant="outline" onClick={() => handleExport("md")}>
              <FileDown className="mr-1.5 h-3 w-3" />
              MD
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport("html")}>
              <FileDown className="mr-1.5 h-3 w-3" />
              HTML
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport("docx")}>
              <FileDown className="mr-1.5 h-3 w-3" />
              Word
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="ml-auto"
            >
              <X className="mr-1 h-3 w-3" />
              关闭
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 嵌套：章节只读查看 */}
      <Dialog open={viewChapter !== null} onOpenChange={(o) => !o && setViewChapter(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {viewChapter && `第 ${viewChapter.chapter_number} 章 · ${viewChapter.title ?? "（未命名）"}`}
            </DialogTitle>
            <DialogDescription>
              只读 · {viewChapter?.word_count.toLocaleString() ?? 0} 字
            </DialogDescription>
          </DialogHeader>
          {viewLoading ? (
            <p className="text-xs text-neutral-400">加载中…</p>
          ) : viewVersion ? (
            <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-md bg-neutral-50 dark:bg-neutral-900/50 p-3 text-sm">
              {viewVersion.content}
            </pre>
          ) : (
            <p className="text-xs text-neutral-400">无内容</p>
          )}
          <div className="flex justify-end gap-2 border-t border-neutral-200 dark:border-neutral-800 pt-3 mt-3">
            {viewChapter && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setVersionChapter(viewChapter);
                  setViewChapter(null);
                }}
              >
                <History className="mr-1.5 h-3 w-3" />
                查看版本历史
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setViewChapter(null)}>
              关闭
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 嵌套：版本历史（复用 Phase 4.6 VersionPanel） */}
      <VersionPanel
        open={versionChapter !== null}
        onOpenChange={(o) => !o && setVersionChapter(null)}
        chapter={versionChapter}
        onRollback={() => {
          // 简化为刷新（实际可重新拉 chapters）
          if (novel) {
            chaptersApi.list(novel.id).then(setChapters).catch(() => {});
          }
          setVersionChapter(null);
        }}
      />
    </>
  );
}
