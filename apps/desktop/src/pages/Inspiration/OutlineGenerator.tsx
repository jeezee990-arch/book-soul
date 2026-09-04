import { useCallback, useState } from "react";
import { toast } from "sonner";
import { outlinesApi, type OutlineGenerationResponse } from "@/api/outlines";
import { ApiError } from "@/api";
import type { GenreDef } from "@/config/genres";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  genre: GenreDef;
  /** Phase 3.4：用作大纲种子的 PLOT（来自父组件 state）。null = 不可生成。 */
  currentPlot: { id: number; summary: string } | null;
}

type OutlineType = "complete" | "freedom";

interface VolumeDisplay {
  name: string;
  summary?: string;
  chapters: { title: string; summary?: string; key_events?: string[] }[];
}

interface CompleteStructure {
  volumes: VolumeDisplay[];
  overall_theme?: string;
}

interface FreedomStructure {
  summary: string;
  key_beats: string[];
  themes: string[];
}

/**
 * 大纲生成（Phase 3.4）。
 *
 * - 调 POST /novels/outlines/generate（自动建 novel + 调 LLM + 入库）
 * - 显示结果：complete 模式 → 分卷/章节树；freedom 模式 → 散文+节拍
 * - 不持久化到前端：后端已入库到 outline 表
 */
export default function OutlineGenerator({ genre, currentPlot }: Props) {
  const [novelName, setNovelName] = useState("");
  const [outlineType, setOutlineType] = useState<OutlineType>("complete");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OutlineGenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    if (!currentPlot) {
      toast.info("请先在下方'我的灵感'里点一个 PLOT 卡加载种子");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await outlinesApi.generate({
        genre: genre.name,
        plot_summary: currentPlot.summary,
        novel_name: novelName.trim() || undefined,
        outline_type: outlineType,
      });
      setResult(resp);
      toast.success(`已生成大纲：${resp.novel_name} / ${resp.outline_type}`);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setError(msg);
      toast.error("大纲生成失败", { description: msg });
    } finally {
      setLoading(false);
    }
  }, [genre.name, currentPlot, novelName, outlineType]);

  const disabled = loading || !currentPlot;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">第四步：生成大纲</CardTitle>
        <CardDescription>
          基于 PLOT 剧情，自动创建作品 + 调 LLM 扩展为大纲（complete：分卷/章；freedom：散文+节拍）。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 当前种子 */}
        <div className="rounded-md border border-dashed border-neutral-300 px-3 py-2 text-xs dark:border-neutral-700">
          {currentPlot ? (
            <span>
              当前种子：<span className="font-mono">PLOT #{currentPlot.id}</span>
              <span className="ml-2 text-neutral-500">（来自'我的灵感'点开）</span>
            </span>
          ) : (
            <span className="text-neutral-500">
              未选种子 —— 去下方"我的灵感"列表点一个 PLOT 卡
            </span>
          )}
        </div>

        {/* 工具栏：作品名 + 类型选择 */}
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="text"
            placeholder={`作品名（留空用 "${genre.name}新作"）`}
            value={novelName}
            onChange={(e) => setNovelName(e.target.value)}
            className="flex-1 min-w-[200px]"
          />
          <div className="flex items-center gap-1 rounded-md border border-neutral-200 dark:border-neutral-800 p-0.5">
            <button
              type="button"
              onClick={() => setOutlineType("complete")}
              className={[
                "rounded px-2 py-1 text-xs",
                outlineType === "complete"
                  ? "bg-neutral-900 text-neutral-50 dark:bg-neutral-100 dark:text-neutral-900"
                  : "text-neutral-600 dark:text-neutral-400",
              ].join(" ")}
            >
              完整版（分卷/章）
            </button>
            <button
              type="button"
              onClick={() => setOutlineType("freedom")}
              className={[
                "rounded px-2 py-1 text-xs",
                outlineType === "freedom"
                  ? "bg-neutral-900 text-neutral-50 dark:bg-neutral-100 dark:text-neutral-900"
                  : "text-neutral-600 dark:text-neutral-400",
              ].join(" ")}
            >
              自由版（散文+节拍）
            </button>
          </div>
          <Button onClick={handleGenerate} disabled={disabled}>
            {loading ? "生成中..." : "生成大纲"}
          </Button>
        </div>

        {error && (
          <p className="text-xs text-destructive">生成失败：{error}</p>
        )}

        {/* 结果展示 */}
        {result && (
          <div className="space-y-3">
            <div className="flex items-center justify-between border-t border-neutral-200 pt-3 dark:border-neutral-800">
              <div>
                <div className="text-sm font-medium">
                  {result.novel_name}（id={result.novel_id}）
                </div>
                <div className="text-[10px] text-neutral-500 font-mono">
                  outline #{result.outline_id} · {result.outline_type} · provider:{" "}
                  {result.provider}
                </div>
              </div>
            </div>

            {result.outline_type === "complete" ? (
              <CompleteView structure={result.structure as unknown as CompleteStructure} />
            ) : (
              <FreedomView structure={result.structure as unknown as FreedomStructure} />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CompleteView({ structure }: { structure: CompleteStructure }) {
  if (!structure?.volumes?.length) {
    return <p className="text-xs text-neutral-500">（无分卷数据）</p>;
  }
  return (
    <div className="space-y-3">
      {structure.overall_theme && (
        <div className="rounded-md border border-neutral-200 dark:border-neutral-800 px-3 py-2 text-xs">
          <span className="text-neutral-500">全篇主题：</span>
          {structure.overall_theme}
        </div>
      )}
      {structure.volumes.map((v, i) => (
        <div
          key={`${i}-${v.name}`}
          className="rounded-md border border-neutral-200 dark:border-neutral-800 p-3"
        >
          <div className="text-sm font-medium">
            第 {toChineseNum(i + 1)} 卷 · {v.name}
          </div>
          {v.summary && (
            <p className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
              {v.summary}
            </p>
          )}
          <ol className="mt-2 space-y-1.5 pl-4 text-xs leading-relaxed">
            {v.chapters.map((c, j) => (
              <li key={`${i}-${j}-${c.title}`} className="list-decimal">
                <span className="font-medium">{c.title}</span>
                {c.summary && (
                  <span className="ml-1 text-neutral-500">— {c.summary}</span>
                )}
                {c.key_events && c.key_events.length > 0 && (
                  <div className="ml-2 mt-0.5 text-[11px] text-neutral-400">
                    关键事件：{c.key_events.join("、")}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}

function FreedomView({ structure }: { structure: FreedomStructure }) {
  return (
    <div className="space-y-3">
      {structure.themes && structure.themes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {structure.themes.map((t) => (
            <span
              key={t}
              className="rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 px-2 py-0.5 text-[11px]"
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <p className="rounded-md border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900 px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap">
        {structure.summary}
      </p>
      {structure.key_beats && structure.key_beats.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wider text-neutral-400">
            关键节拍
          </div>
          <ol className="space-y-1 pl-5 text-xs leading-relaxed">
            {structure.key_beats.map((b, i) => (
              <li key={i} className="list-decimal">
                {b}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function toChineseNum(n: number): string {
  const m = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"];
  if (n < 10) return m[n];
  if (n < 20) return `十${n === 10 ? "" : m[n - 10]}`;
  if (n < 100) return `${m[Math.floor(n / 10)]}十${n % 10 === 0 ? "" : m[n % 10]}`;
  return String(n);
}
