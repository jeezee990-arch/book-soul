import { useState } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import EmptyState from "@/components/layout/EmptyState";

/** 质检 —— 5 维度评分占位 + 报告占位（Phase 3.9 静态框架，Phase 5 接入真实 LLM） */

interface DimensionScore {
  key: string;
  label: string;
  score: number; // 0-100
  description: string;
}

const MOCK_DIMENSIONS: DimensionScore[] = [
  {
    key: "writing",
    label: "文笔",
    score: 82,
    description: "句式流畅度、用词精准度、节奏控制",
  },
  {
    key: "logic",
    label: "逻辑",
    score: 75,
    description: "情节合理性、伏笔回收、因果链",
  },
  {
    key: "pacing",
    label: "节奏",
    score: 68,
    description: "起承转合、紧张度曲线、章节间过渡",
  },
  {
    key: "consistency",
    label: "一致性",
    score: 91,
    description: "人物性格前后一致、世界观不冲突",
  },
  {
    key: "genre",
    label: "题材合规",
    score: 88,
    description: "符合题材套路与读者期待",
  },
];

function scoreColor(s: number): string {
  if (s >= 85) return "text-emerald-500";
  if (s >= 70) return "text-amber-500";
  return "text-rose-500";
}

function scoreBarColor(s: number): string {
  if (s >= 85) return "bg-emerald-500";
  if (s >= 70) return "bg-amber-500";
  return "bg-rose-500";
}

export default function QualityCheck() {
  const [busy, setBusy] = useState(false);
  const [hasReport, setHasReport] = useState(false);

  const handleRun = () => {
    setBusy(true);
    // MOCK: 实际接入在 Phase 5
    setTimeout(() => {
      setHasReport(true);
      setBusy(false);
      toast.success("质检完成（占位数据）");
    }, 800);
  };

  const avg =
    MOCK_DIMENSIONS.reduce((sum, d) => sum + d.score, 0) /
    MOCK_DIMENSIONS.length;

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">质检</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          人物一致 · 剧情合理 · 文本质量自动评估（Phase 5 接入 LLM）。
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">运行质检</CardTitle>
          <CardDescription>
            选章节 → 自动评分（5 维度）→ 看报告（当前为占位流程）。
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3 flex-wrap">
          <Button onClick={handleRun} disabled={busy}>
            {busy ? "质检中..." : "试运行（占位）"}
          </Button>
          <span className="text-xs text-neutral-500">
            真实 LLM 评分在 Phase 5 接入；当前显示 mock 数据
          </span>
        </CardContent>
      </Card>

      {!hasReport ? (
        <EmptyState
          icon="📊"
          title="还没有质检报告"
          description='点上面「试运行」看一份占位报告；Phase 5 会用本地 ollama 跑真实 LLM 评分。'
        />
      ) : (
        <div className="space-y-3">
          {/* 总分 */}
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle className="text-base">综合评分</CardTitle>
                <span
                  className={`text-3xl font-semibold ${scoreColor(avg)}`}
                >
                  {avg.toFixed(1)}
                </span>
              </div>
              <CardDescription>
                5 维度均分（占位数据） · 章节 #42 · 模型：ollama / qwen2.5:14b
              </CardDescription>
            </CardHeader>
          </Card>

          {/* 5 维度 */}
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {MOCK_DIMENSIONS.map((d) => (
              <Card key={d.key}>
                <CardHeader>
                  <div className="flex items-baseline justify-between">
                    <CardTitle className="text-base">{d.label}</CardTitle>
                    <span
                      className={`text-lg font-semibold ${scoreColor(d.score)}`}
                    >
                      {d.score}
                    </span>
                  </div>
                  <CardDescription className="text-xs">
                    {d.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-2 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                    <div
                      className={`h-full ${scoreBarColor(d.score)} transition-all`}
                      style={{ width: `${d.score}%` }}
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 报告导出占位 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">报告导出</CardTitle>
              <CardDescription>Phase 5 接入：导出 PDF / markdown</CardDescription>
            </CardHeader>
            <CardContent className="flex gap-2">
              <Button variant="outline" size="sm" disabled>
                导出 markdown
              </Button>
              <Button variant="outline" size="sm" disabled>
                导出 PDF
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  );
}
