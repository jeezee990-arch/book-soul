import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

/** 质检 —— Phase 5 才接入 LLM 评分，本阶段先占位 */
export default function QualityCheck() {
  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">质检</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          人物一致性 · 剧情合理性 · 文本质量自动评估。
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">即将上线</CardTitle>
          <CardDescription>
            质检功能在 Phase 5 接入 LLM 后开放。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            size="sm"
            onClick={() => toast.info("敬请期待", { description: "Phase 5 接入" })}
          >
            试运行
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
