import { useEffect, useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
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

/** 作品库 —— 列出所有作品 */
export default function Library() {
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
          onClick={() => toast.info("敬请期待", { description: "Phase 3 接入" })}
        >
          新建作品
        </Button>
      </header>

      {loading && <p className="text-sm text-neutral-400">加载中...</p>}

      {error && !loading && (
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="text-base text-destructive">
              加载失败
            </CardTitle>
            <CardDescription className="font-mono text-xs">
              {error}
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="border border-dashed border-neutral-300 dark:border-neutral-800 rounded-lg p-12 text-center">
          <p className="text-sm text-neutral-400 dark:text-neutral-500">
            暂无作品
          </p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((n) => (
          <Card key={n.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{n.name}</CardTitle>
                <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                  {n.genre}
                </span>
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
    </section>
  );
}
