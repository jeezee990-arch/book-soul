import { useEffect, useState } from "react";
import { FileDown, ExternalLink, BookOpen } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import EmptyState from "@/components/layout/EmptyState";
import { novelsApi, downloadExportFile } from "@/api/novels";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";

interface Props {
  /** 仅显示 word_count > 0 的作品（藏书馆模式） */
  withChaptersOnly: boolean;
  onSelect: (novel: Novel) => void;
}

/** 作品列表（Phase 6.2：可过滤"有章节"模式）。 */
export default function LibraryList({ withChaptersOnly, onSelect }: Props) {
  const [items, setItems] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    novelsApi
      .list()
      .then(async (data) => {
        if (cancelled) return;
        if (!withChaptersOnly) {
          setItems(data);
          return;
        }
        // 过滤有正文的（任一章节 word_count > 0）
        const filtered: Novel[] = [];
        for (const n of data) {
          try {
            const { chaptersApi } = await import("@/api/chapters");
            const chs = await chaptersApi.list(n.id);
            if (chs.some((c) => c.word_count > 0)) {
              filtered.push(n);
            }
          } catch {
            // 跳过单条失败
          }
        }
        if (!cancelled) setItems(filtered);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setError(msg);
          toast.error("拉取作品失败", { description: msg });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [withChaptersOnly]);

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

  return (
    <div className="space-y-3">
      <span className="text-xs text-neutral-500">共 {items.length} 部</span>

      {loading && <LoadingSkeleton rows={4} height={100} />}
      {error && !loading && <ErrorState message={error} />}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon={withChaptersOnly ? "📖" : "📚"}
          title={withChaptersOnly ? "藏书馆还是空的" : "还没有作品"}
          description={
            withChaptersOnly
              ? "先去创作页生成章节内容；填了正文的作品会出现在这里"
              : "去灵感园完成三步流程（关键词 → 剧情 → 大纲），自动创建作品"
          }
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="space-y-3">
          {items.map((n) => (
            <Card key={n.id}>
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-neutral-400" />
                    <CardTitle className="text-base">{n.name}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                      {n.genre}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs"
                      onClick={() => onSelect(n)}
                    >
                      <ExternalLink className="mr-1 h-3 w-3" />
                      进入详情
                    </Button>
                  </div>
                </div>
                {n.description && (
                  <CardDescription className="line-clamp-2">
                    {n.description}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="text-xs text-neutral-500 dark:text-neutral-400 flex gap-3 flex-wrap items-center">
                <span>状态：{n.status}</span>
                <span>大纲：{n.outline_mode ?? "—"}</span>
                <span className="ml-auto flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => handleExport(n, "md")}
                  >
                    <FileDown className="mr-1 h-3 w-3" />
                    MD
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => handleExport(n, "html")}
                  >
                    <FileDown className="mr-1 h-3 w-3" />
                    HTML
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[10px]"
                    onClick={() => handleExport(n, "docx")}
                  >
                    <FileDown className="mr-1 h-3 w-3" />
                    Word
                  </Button>
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
