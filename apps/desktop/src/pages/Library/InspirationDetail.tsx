import { useState } from "react";
import { toast } from "sonner";
import { Download, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { downloadExportFile, novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { InspirationDetail } from "@/api/inspirations";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  keyword: "关键词",
  plot: "剧情",
  snippet: "片段",
  image: "画面",
  note: "备注",
};

function renderContent(detail: InspirationDetail) {
  const c = detail.content ?? {};
  switch (detail.type) {
    case "keyword":
      return (
        <div className="flex flex-wrap gap-2">
          {((c.words as string[] | undefined) ?? []).map((w) => (
            <span
              key={w}
              className="rounded-md bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-200 px-2 py-1 text-sm"
            >
              {w}
            </span>
          ))}
        </div>
      );
    case "plot":
      return (
        <div className="space-y-3">
          <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
            {(c.summary as string | undefined) ?? ""}
          </p>
          {Array.isArray(c.beats) && (c.beats as string[]).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-neutral-500 mb-1.5">
                关键节拍
              </h4>
              <ol className="list-decimal pl-5 text-sm text-neutral-700 dark:text-neutral-300 space-y-0.5">
                {(c.beats as string[]).map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      );
    case "snippet":
    case "note":
      return (
        <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
          {(c.text as string | undefined) ?? ""}
        </p>
      );
    case "image":
      return (
        <p className="text-sm text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
          {(c.description as string | undefined) ?? ""}
        </p>
      );
    default:
      return (
        <pre className="text-xs font-mono text-neutral-600 dark:text-neutral-400 whitespace-pre-wrap">
          {JSON.stringify(c, null, 2)}
        </pre>
      );
  }
}

function renderOutline(structure: Record<string, unknown> | null | undefined) {
  if (!structure) return <p className="text-xs text-neutral-400">暂无大纲</p>;
  return (
    <pre className="text-xs font-mono text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap rounded-md bg-neutral-50 dark:bg-neutral-900/50 p-3 max-h-96 overflow-auto">
      {JSON.stringify(structure, null, 2)}
    </pre>
  );
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail: InspirationDetail | null;
}

/** 灵感详情 dialog（Phase 6.1）：基础 + 人物卡 + 大纲 + 章节。 */
export default function InspirationDetail({
  open,
  onOpenChange,
  detail,
}: Props) {
  const [exporting, setExporting] = useState(false);

  async function handleExport(format: "md" | "html" | "docx") {
    if (!detail?.novel) return;
    setExporting(true);
    try {
      const file = await novelsApi.export(detail.novel.id, format);
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    } finally {
      setExporting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-200 px-1.5 py-0.5 text-xs">
              {TYPE_LABEL[detail?.type ?? ""] ?? detail?.type ?? "?"}
            </span>
            <span>灵感 #{detail?.id}</span>
            {detail?.source && (
              <span className="text-xs text-neutral-500 ml-2">
                来源：{detail.source}
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            {detail?.created_at
              ? `创建于 ${new Date(detail.created_at).toLocaleString("zh-CN", { hour12: false })}`
              : ""}
          </DialogDescription>
        </DialogHeader>

        {detail && (
          <div className="space-y-4">
            {/* tags */}
            {detail.tags.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {detail.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 text-[10px] text-neutral-500"
                  >
                    #{t}
                  </span>
                ))}
              </div>
            )}

            {/* 灵感内容 */}
            <section>
              <h3 className="text-sm font-medium mb-2">灵感内容</h3>
              {renderContent(detail)}
            </section>

            {/* 关联作品 */}
            {detail.novel ? (
              <Tabs defaultValue="characters">
                <TabsList>
                  <TabsTrigger value="characters">
                    人物卡（{detail.novel.characters.length}）
                  </TabsTrigger>
                  <TabsTrigger value="outline">大纲</TabsTrigger>
                  <TabsTrigger value="chapters">
                    章节（{detail.novel.chapters.length}）
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="characters" className="space-y-2 mt-3 max-h-80 overflow-auto">
                  {detail.novel.characters.length === 0 ? (
                    <p className="text-xs text-neutral-400">暂无人物卡</p>
                  ) : (
                    detail.novel.characters.map((c) => (
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
                  {renderOutline(detail.novel.outline_structure)}
                </TabsContent>
                <TabsContent
                  value="chapters"
                  className="mt-3 space-y-1.5 max-h-80 overflow-auto"
                >
                  {detail.novel.chapters.length === 0 ? (
                    <p className="text-xs text-neutral-400">暂无章节</p>
                  ) : (
                    detail.novel.chapters.map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between rounded-md border border-neutral-200 dark:border-neutral-800 px-3 py-1.5 text-sm"
                      >
                        <span>
                          第 {c.chapter_number} 章 · {c.title ?? "（未命名）"}
                        </span>
                        <span className="text-xs text-neutral-500">
                          {c.word_count.toLocaleString()} 字 · {c.status}
                        </span>
                      </div>
                    ))
                  )}
                </TabsContent>
              </Tabs>
            ) : (
              <p className="text-xs text-neutral-400">通用灵感（未关联作品）</p>
            )}

            {/* 操作 */}
            <div className="flex items-center gap-2 border-t border-neutral-200 dark:border-neutral-800 pt-3">
              {detail.novel && (
                <>
                  <span className="text-xs text-neutral-500">导出作品：</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleExport("md")}
                    disabled={exporting}
                  >
                    <Download className="mr-1.5 h-3 w-3" />
                    MD
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleExport("html")}
                    disabled={exporting}
                  >
                    <Download className="mr-1.5 h-3 w-3" />
                    HTML
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleExport("docx")}
                    disabled={exporting}
                  >
                    <Download className="mr-1.5 h-3 w-3" />
                    Word
                  </Button>
                </>
              )}
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
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
