import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  inspirationsApi,
  type PlotVersion,
} from "@/api/inspirations";
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

interface Props {
  genre: GenreDef;
  /** 父组件持有的已选关键词（来自 KeywordBoard）。 */
  selectedKeywords: Set<string>;
  /** Phase 3.4：被选为"大纲种子"的剧情（null = 还没选）。 */
  currentPlot: { id: number; summary: string } | null;
  /** 父组件的清空回调（点"清空选中"时调）。 */
  onClearCurrentPlot?: () => void;
}

interface PlotState {
  versions: PlotVersion[];
  loading: boolean;
  error: string | null;
  provider: string;
  model: string;
}

const INITIAL: PlotState = {
  versions: [],
  loading: false,
  error: null,
  provider: "",
  model: "",
};

const N_VERSIONS = 3;

/**
 * 简要剧情生成（Phase 3.3）。
 *
 * - 调 POST /inspirations/generate-plot 拿 n 个版本
 * - 每个版本可单独保存到灵感库（type=plot）
 * - 生成失败 → toast + 错误提示
 */
export default function PlotGenerator({
  genre,
  selectedKeywords,
  currentPlot,
  onClearCurrentPlot,
}: Props) {
  const [state, setState] = useState<PlotState>(INITIAL);
  const [savingIdx, setSavingIdx] = useState<number | null>(null);

  const handleGenerate = useCallback(async () => {
    if (selectedKeywords.size === 0) {
      toast.info("请先选择灵感词", {
        description: "到第二步的词库里点选关键词",
      });
      return;
    }
    setState({ ...INITIAL, loading: true });
    try {
      const resp = await inspirationsApi.generatePlot({
        genre: genre.name,
        keywords: Array.from(selectedKeywords),
        n_versions: N_VERSIONS,
      });
      setState({
        versions: resp.versions,
        loading: false,
        error: null,
        provider: resp.provider,
        model: resp.model,
      });
      toast.success(`已生成 ${resp.versions.length} 个剧情`);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setState({ ...INITIAL, error: msg });
      toast.error("剧情生成失败", { description: msg });
    }
  }, [genre.name, selectedKeywords]);

  const handleSave = useCallback(
    async (v: PlotVersion) => {
      setSavingIdx(v.index);
      try {
        await inspirationsApi.create({
          novel_id: null,
          type: "plot",
          content: { summary: v.summary, beats: [] },
          source: `PlotGenerator:${genre.id}`,
          tags: [genre.id, "ai_generated", `v${v.index}`],
        });
        toast.success(`已保存版本 ${v.index} 到草稿库`);
      } catch (e: unknown) {
        const msg = e instanceof ApiError ? e.message : String(e);
        toast.error("保存失败", { description: msg });
      } finally {
        setSavingIdx(null);
      }
    },
    [genre.id],
  );

  const disabled = state.loading || selectedKeywords.size === 0;

  return (
    <Card>
      {/* Phase 3.4：当前被选作大纲种子的剧情（来自"我的灵感"PLOT 卡点开） */}
      {currentPlot && (
        <div className="mx-6 mt-4 rounded-md border border-neutral-300 bg-neutral-50 p-3 dark:border-neutral-700 dark:bg-neutral-900">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium text-neutral-600 dark:text-neutral-400">
              📌 已选为大纲种子（PLOT #{currentPlot.id}）
            </span>
            {onClearCurrentPlot && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onClearCurrentPlot}
              >
                清空
              </Button>
            )}
          </div>
          <p className="line-clamp-3 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">
            {currentPlot.summary}
          </p>
        </div>
      )}
      <CardHeader>
        <CardTitle className="text-base">第三步：生成简要剧情</CardTitle>
        <CardDescription>
          基于已选关键词 + {genre.name} 题材，AI 生成 {N_VERSIONS} 个不同角度的剧情。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-neutral-500">
            将用 {selectedKeywords.size} 个关键词生成 {N_VERSIONS} 个版本
          </span>
          <Button onClick={handleGenerate} disabled={disabled}>
            {state.loading ? "生成中..." : `生成 ${N_VERSIONS} 个剧情`}
          </Button>
        </div>

        {state.error && (
          <p className="text-xs text-destructive">生成失败：{state.error}</p>
        )}

        {state.versions.length > 0 && (
          <>
            <div className="space-y-3">
              {state.versions.map((v) => (
                <Card key={v.index}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm">版本 {v.index}</CardTitle>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSave(v)}
                        disabled={savingIdx === v.index}
                      >
                        {savingIdx === v.index ? "保存中..." : "💾 保存"}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">
                      {v.summary}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
            <p className="font-mono text-[10px] text-neutral-400">
              provider: {state.provider}
              {state.model && ` · model: ${state.model}`}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
