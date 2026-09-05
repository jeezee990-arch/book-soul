import { useEffect, useState } from "react";
import { Download, FileDown, BookOpen, Lightbulb } from "lucide-react";
import { toast } from "sonner";
import { downloadExportFile, novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import InspirationList from "./InspirationList";
import InspirationDetail from "./InspirationDetail";
import type { InspirationDetail as InspirationDetailType } from "@/api/inspirations";

/** 作品库 —— 作品列表 + 灵感库（Phase 6.1 tab 切换） */
export default function Library() {
  const [tab, setTab] = useState<"novels" | "inspirations">("novels");
  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">作品库</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          作品管理 · 灵感库 · 人物卡 · 章节集中管理。
        </p>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as "novels" | "inspirations")}>
        <TabsList>
          <TabsTrigger value="novels">
            <BookOpen className="mr-1.5 h-3.5 w-3.5" />
            作品
          </TabsTrigger>
          <TabsTrigger value="inspirations">
            <Lightbulb className="mr-1.5 h-3.5 w-3.5" />
            灵感库
          </TabsTrigger>
        </TabsList>
        <TabsContent value="novels" className="mt-4">
          <NovelList />
        </TabsContent>
        <TabsContent value="inspirations" className="mt-4">
          <InspirationTab />
        </TabsContent>
      </Tabs>
    </section>
  );
}

/* ===== 作品列表（Phase 3.9 沿用 + Phase 4.7 导出）===== */

function NovelList() {
  const [items, setItems] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
  }, []);

  async function handleExport(novel: Novel, format: "md" | "html" | "docx") {
    try {
      const file = await novelsApi.export(novel.id, format);
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      if (format === "docx" && msg.includes("python-docx")) {
        toast.error("Word 导出未启用", { description: "后端需安装 python-docx" });
      } else {
        toast.error("导出失败", { description: msg });
      }
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-xs text-neutral-500">共 {items.length} 部作品</span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => toast.info("敬请期待", { description: "Phase 4 接入" })}
        >
          新建作品
        </Button>
      </div>

      {loading && <LoadingSkeleton rows={4} height={100} />}
      {error && !loading && <ErrorState message={error} />}

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
                        <DropdownMenuItem onClick={() => handleExport(n, "docx")}>
                          <FileDown className="mr-2 h-3.5 w-3.5" />
                          Word (.docx)
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
                {n.read_only && <span className="text-amber-500">只读</span>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ===== 灵感库 Tab（Phase 6.1）===== */

function InspirationTab() {
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<InspirationDetailType | null>(null);
  const [open, setOpen] = useState(false);

  return (
    <>
      <InspirationList
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        onSelect={(d) => {
          setSelected(d);
          setOpen(true);
        }}
      />
      <InspirationDetail
        open={open}
        onOpenChange={setOpen}
        detail={selected}
      />
    </>
  );
}
