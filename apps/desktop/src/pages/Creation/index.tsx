import { useEffect, useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Novel, Chapter } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** 创作 —— 选作品 → 章节列表 */
export default function Creation() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadingNovels, setLoadingNovels] = useState(true);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    if (novelId === null) return;
    let cancelled = false;
    setLoadingChapters(true);
    chaptersApi
      .list(novelId)
      .then((data) => {
        if (!cancelled) setChapters(data);
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

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">创作</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          章节编辑与生成 · 人物卡一致性 · 上下文记忆。
        </p>
      </header>

      {error && (
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

      {!error && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-neutral-500">作品：</span>
          <Select
            value={novelId ? String(novelId) : undefined}
            onValueChange={(v) => setNovelId(Number(v))}
            disabled={loadingNovels || novels.length === 0}
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="选择作品" />
            </SelectTrigger>
            <SelectContent>
              {novels.map((n) => (
                <SelectItem key={n.id} value={String(n.id)}>
                  {n.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {loadingChapters && (
        <p className="text-sm text-neutral-400">加载章节中...</p>
      )}

      {!loadingChapters && novelId !== null && chapters.length === 0 && (
        <div className="border border-dashed border-neutral-300 dark:border-neutral-800 rounded-lg p-12 text-center">
          <p className="text-sm text-neutral-400 dark:text-neutral-500">
            该作品暂无章节
          </p>
        </div>
      )}

      <div className="space-y-3">
        {chapters.map((c) => (
          <Card key={c.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  第 {c.chapter_number} 章 · {c.title ?? "（未命名）"}
                </CardTitle>
                <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                  {c.status}
                </span>
              </div>
              {c.outline && (
                <CardDescription className="line-clamp-2">
                  {c.outline}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="text-xs text-neutral-500 dark:text-neutral-400">
              字数：{c.word_count.toLocaleString()}
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
