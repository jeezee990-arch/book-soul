import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2, ExternalLink } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import EmptyState from "@/components/layout/EmptyState";
import { inspirationsApi } from "@/api/inspirations";
import type { InspirationDetail } from "@/api/inspirations";
import { novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { Inspiration, Novel } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  keyword: "关键词",
  plot: "剧情",
  snippet: "片段",
  image: "画面",
  note: "备注",
};

const TYPE_TONE: Record<string, string> = {
  keyword: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200",
  plot: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200",
  snippet: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200",
  image: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
  note: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200",
};

function summarizeContent(ins: Inspiration): string {
  const c = ins.content ?? {};
  switch (ins.type) {
    case "keyword":
      return (c.words as string[] | undefined)?.join(" · ") ?? "（空）";
    case "plot":
      return (c.summary as string | undefined)?.slice(0, 100) ?? "（空）";
    case "snippet":
      return (c.text as string | undefined)?.slice(0, 100) ?? "（空）";
    case "image":
      return (c.description as string | undefined)?.slice(0, 100) ?? "（空）";
    case "note":
      return (c.text as string | undefined)?.slice(0, 100) ?? "（空）";
    default:
      return JSON.stringify(c).slice(0, 100);
  }
}

interface Props {
  typeFilter: string | null;
  onTypeFilterChange: (v: string | null) => void;
  onSelect: (detail: InspirationDetail) => void;
}

/** 灵感库列表（Phase 6.1）。 */
export default function InspirationList({
  typeFilter,
  onTypeFilterChange,
  onSelect,
}: Props) {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([inspirationsApi.list(typeFilter ? { type: typeFilter } : undefined), novelsApi.list()])
      .then(([insps, nvs]) => {
        if (!cancelled) {
          setItems(insps);
          setNovels(nvs);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [typeFilter]);

  const novelNameById = new Map(novels.map((n) => [n.id, n.name] as const));

  async function handleOpen(ins: Inspiration) {
    try {
      const detail = await inspirationsApi.detail(ins.id);
      onSelect(detail);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("加载详情失败", { description: msg });
    }
  }

  async function handleDelete(ins: Inspiration) {
    if (!confirm(`确认删除灵感 #${ins.id}？此操作不可恢复。`)) return;
    setBusyId(ins.id);
    try {
      await inspirationsApi.remove(ins.id);
      setItems((prev) => prev.filter((i) => i.id !== ins.id));
      toast.success("已删除");
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("删除失败", { description: msg });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-neutral-500">类型筛选</span>
        <Select
          value={typeFilter ?? "all"}
          onValueChange={(v) => onTypeFilterChange(v === "all" ? null : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="keyword">关键词</SelectItem>
            <SelectItem value="plot">剧情</SelectItem>
            <SelectItem value="snippet">片段</SelectItem>
            <SelectItem value="image">画面</SelectItem>
            <SelectItem value="note">备注</SelectItem>
          </SelectContent>
        </Select>
        <span className="ml-auto text-xs text-neutral-500">共 {items.length} 条</span>
      </div>

      {loading && <LoadingSkeleton rows={4} height={80} />}
      {error && !loading && <ErrorState message={error} />}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon="💡"
          title="还没有灵感"
          description="去灵感园保存关键词 / 剧情 / 片段 / 画面 / 备注"
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="space-y-2">
          {items.map((ins) => (
            <Card
              key={ins.id}
              className="hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors"
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px]",
                      TYPE_TONE[ins.type] ?? TYPE_TONE.note,
                    )}
                  >
                    {TYPE_LABEL[ins.type] ?? ins.type}
                  </span>
                  <CardTitle className="text-sm">#{ins.id}</CardTitle>
                  {ins.novel_id !== null && (
                    <span className="text-[10px] text-neutral-500 flex items-center gap-1">
                      <ExternalLink className="h-3 w-3" />
                      {novelNameById.get(ins.novel_id) ?? `novel #${ins.novel_id}`}
                    </span>
                  )}
                  <span className="ml-auto text-[10px] text-neutral-400">
                    {new Date(ins.created_at).toLocaleString("zh-CN", { hour12: false })}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-neutral-700 dark:text-neutral-300 line-clamp-2">
                  {summarizeContent(ins)}
                </p>
                {ins.tags.length > 0 && (
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {ins.tags.map((t: string) => (
                      <span
                        key={t}
                        className="rounded border border-neutral-200 dark:border-neutral-800 px-1.5 py-0.5 text-[10px] text-neutral-500"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => handleOpen(ins)}>
                    <ExternalLink className="mr-1.5 h-3 w-3" />
                    查看详情
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(ins)}
                    disabled={busyId === ins.id}
                  >
                    <Trash2 className="mr-1.5 h-3 w-3" />
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
