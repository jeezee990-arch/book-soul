import { useEffect, useState } from "react";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import { ApiError } from "@/api";
import type { Inspiration } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/** 灵感园 —— 列出已有灵感（Phase 3 扩展：词库 / 剧情生成 / 人物卡） */
export default function Inspiration() {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    inspirationsApi
      .list()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          setError(msg);
          toast.error("拉取灵感失败", { description: msg });
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
          <h1 className="text-2xl font-semibold tracking-tight">灵感园</h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            从题材、词库到剧情大纲与人物卡的完整开书流程。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => toast.info("敬请期待", { description: "Phase 3 接入" })}
        >
          新建灵感
        </Button>
      </header>

      {loading && (
        <p className="text-sm text-neutral-400">加载中...</p>
      )}

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
            暂无灵感
          </p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((it) => (
          <Card key={it.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {summarize(it)}
                </CardTitle>
                <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                  {it.type}
                </span>
              </div>
              {it.source && (
                <CardDescription>来源：{it.source}</CardDescription>
              )}
            </CardHeader>
            {it.tags.length > 0 && (
              <CardContent className="text-xs text-neutral-500 dark:text-neutral-400">
                标签：{it.tags.join("、")}
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}

function summarize(it: Inspiration): string {
  const c = it.content;
  if (typeof c.summary === "string") return c.summary;
  if (typeof c.text === "string") return c.text;
  if (typeof c.description === "string") return c.description;
  if (Array.isArray(c.words)) return c.words.join("、");
  return `灵感 #${it.id}`;
}
