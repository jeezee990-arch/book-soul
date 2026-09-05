import { useEffect, useState } from "react";
import { Download, FileDown } from "lucide-react";
import { toast } from "sonner";
import { downloadExportFile, novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import EmptyState from "@/components/layout/EmptyState";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";

/** 作品库 —— 列出所有作品（Phase 3.9：复用共用 layout 组件） */
export default function Library() {
  const [items, setItems] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    novelsApi
      .list()
      .then((data) => {
        if (!cancelled) setItems(data);
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
  };

  async function handleExport(novel: Novel, format: "md" | "html" | "docx") {
    try {
      const file = await novelsApi.export(novel.id, format);
      if (format === "docx") {
        toast.info("Word 导出提示", {
          description: "docx 需后端安装 python-docx；当前返回 501。",
        });
      }
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    }
  }

  useEffect(() => {
    return load();
  }, []);

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="space-y-1.5">
          <h1 className="text-2xl font-semibold tracking-tight">作品库</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            所有作品 · 人物卡 · 章节的集中管理。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            toast.info("敬请期待", { description: "Phase 4 接入" })
          }
        >
          新建作品
        </Button>
      </header>

      {loading && <LoadingSkeleton rows={4} height={100} />}

      {error && !loading && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon="📚"
          title="还没有作品"
          description="去灵感园完成三步流程（关键词 → 剧情 → 大纲），自动创建作品并入库到这里。"
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="space-y-3">
          {items.map((n) => (
            <Card key={n.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{n.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                      {n.genre}
                    </span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
                          <Download className="mr-1 h-3 w-3" />
                          导出
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleExport(n, "md")}>
                          <FileDown className="mr-2 h-3.5 w-3.5" />
                          Markdown
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleExport(n, "html")}>
                          <FileDown className="mr-2 h-3.5 w-3.5" />
                          HTML
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleExport(n, "docx")}
                          disabled
                        >
                          <FileDown className="mr-2 h-3.5 w-3.5" />
                          Word (待装包)
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
                {n.description && (
                  <CardDescription className="line-clamp-2">
                    {n.description}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent className="text-xs text-neutral-500 dark:text-neutral-400 flex gap-4 flex-wrap">
                <span>状态：{n.status}</span>
                <span>文风：{n.style ?? "—"}</span>
                <span>大纲：{n.outline_mode ?? "—"}</span>
                {n.read_only && (
                  <span className="text-amber-500">只读</span>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
