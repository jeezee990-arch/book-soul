import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import type { OutlineGenerationResponse } from "@/api/outlines";
import { ApiError } from "@/api";
import type { Inspiration } from "@/lib/types";
import { getGenreDef, type GenreDef } from "@/config/genres";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import GenreSelect from "./GenreSelect";
import KeywordBoard from "./KeywordBoard";
import PlotGenerator from "./PlotGenerator";
import OutlineGenerator from "./OutlineGenerator";
import CharacterManager from "./CharacterManager";
import SavePanel from "./SavePanel";

/** 灵感园 —— 列出已有灵感（Phase 3 扩展：词库 / 剧情生成 / 人物卡） */
export default function Inspiration() {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Phase 3.2: 提升选中的题材为父 state
  const [selectedGenre, setSelectedGenre] = useState<GenreDef | null>(null);
  // Phase 3.3: 提升选中的关键词为父 state，供 PlotGenerator 消费
  const [selectedKeywords, setSelectedKeywords] = useState<Set<string>>(
    () => new Set(),
  );
  // Phase 3.4: 当前被选作大纲种子的 PLOT（null = 没选）
  const [currentPlot, setCurrentPlot] = useState<{
    id: number;
    summary: string;
  } | null>(null);
  // Phase 3.6: 大纲生成成功后保存 (novelId, novelName, structure)，供 CharacterManager / SavePanel 使用
  const [latestOutline, setLatestOutline] = useState<{
    novelId: number;
    novelName: string;
    structure: Record<string, unknown>;
  } | null>(null);

  const handleGenreChange = useCallback((g: GenreDef | null) => {
    setSelectedGenre(g);
    // 切题材时清空旧关键词（避免跨题材污染）
    setSelectedKeywords(new Set());
  }, []);

  // Phase 3.3: 点开历史 KEYWORD 卡 → 切到该题材 + 加载关键词到工作区
  const handleLoadKeyword = useCallback(
    (it: Inspiration) => {
      const words = Array.isArray(it.content.words)
        ? (it.content.words as unknown[]).filter(
            (w): w is string => typeof w === "string",
          )
        : [];
      if (words.length === 0) {
        toast.error("该 KEYWORD 草稿没有有效词条");
        return;
      }
      // 从 tags[0] 拿 genre_id（保存时 tags = [genre_id, "draft"]）
      const genreId = it.tags?.[0];
      const g = genreId ? getGenreDef(genreId) : null;
      if (g) {
        setSelectedGenre(g);
      } else {
        toast.warning("找不到原题材", {
          description: `tags[0]=${String(genreId)}，已保留当前题材`,
        });
      }
      setSelectedKeywords(new Set(words));
      toast.success(`已加载 ${words.length} 个关键词到工作区`);
    },
    [],
  );

  // Phase 3.4: 点开历史 PLOT 卡 → 选为大纲种子
  const handleLoadPlot = useCallback((it: Inspiration) => {
    const summary =
      typeof it.content.summary === "string" ? it.content.summary : "";
    if (!summary) {
      toast.error("该 PLOT 草稿没有有效剧情内容");
      return;
    }
    setCurrentPlot({ id: it.id, summary });
    toast.success(`已选 PLOT #${it.id} 作为大纲种子`);
  }, []);

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
          onClick={() =>
            toast.info("敬请期待", { description: "Phase 3 接入" })
          }
        >
          新建灵感
        </Button>
      </header>

      {/* Phase 3.1：题材选择 + 词库预览 */}
      <GenreSelect selected={selectedGenre} onSelect={handleGenreChange} />

      {/* Phase 3.2：灵感词交互（仅在选了题材后展示） */}
      {selectedGenre && (
        <KeywordBoard
          genre={selectedGenre}
          selected={selectedKeywords}
          onSelectionChange={setSelectedKeywords}
        />
      )}

      {/* Phase 3.3：剧情生成（仅在选了题材后展示） */}
      {selectedGenre && (
        <PlotGenerator
          genre={selectedGenre}
          selectedKeywords={selectedKeywords}
          currentPlot={currentPlot}
          onClearCurrentPlot={() => setCurrentPlot(null)}
        />
      )}

      {/* Phase 3.4：大纲生成（仅在选了题材后展示） */}
      {selectedGenre && (
        <OutlineGenerator
          genre={selectedGenre}
          currentPlot={currentPlot}
          onGenerated={(resp: OutlineGenerationResponse) => {
            setLatestOutline({
              novelId: resp.novel_id,
              novelName: resp.novel_name,
              structure: resp.structure,
            });
          }}
        />
      )}

      {/* Phase 3.6：人物卡管理（仅在大纲生成后展示） */}
      {selectedGenre && latestOutline && (
        <CharacterManager
          novelId={latestOutline.novelId}
          outline={latestOutline.structure}
          genre={selectedGenre.name}
        />
      )}

      {/* Phase 3.8：保存 / 导出（仅在大纲生成后展示） */}
      {latestOutline && (
        <SavePanel
          novelId={latestOutline.novelId}
          novelName={latestOutline.novelName}
        />
      )}

      {/* 已有灵感列表（保留） */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
          我的灵感
        </h2>
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
              暂无灵感
            </p>
          </div>
        )}

        {items.map((it) => {
          // 可点的卡：KEYWORD 加载到工作区 / PLOT 选为大纲种子
          const isKeyword = it.type === "keyword";
          const isPlot = it.type === "plot";
          const isClickable = isKeyword || isPlot;
          const handleClick = isKeyword
            ? () => handleLoadKeyword(it)
            : isPlot
              ? () => handleLoadPlot(it)
              : undefined;
          const hint = isKeyword
            ? "点击加载 →"
            : isPlot
              ? "点击作为大纲种子 →"
              : "";
          return (
            <Card
              key={it.id}
              className={
                isClickable
                  ? "cursor-pointer transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900"
                  : ""
              }
              onClick={handleClick}
              role={isClickable ? "button" : undefined}
              tabIndex={isClickable ? 0 : undefined}
              onKeyDown={
                isClickable
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleClick?.();
                      }
                    }
                  : undefined
              }
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    {summarize(it)}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {isClickable && (
                      <span className="text-[10px] text-neutral-400">{hint}</span>
                    )}
                    <span className="text-[10px] uppercase tracking-wider text-neutral-400 border border-neutral-200 dark:border-neutral-800 rounded px-1.5 py-0.5">
                      {it.type}
                    </span>
                  </div>
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
          );
        })}
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
