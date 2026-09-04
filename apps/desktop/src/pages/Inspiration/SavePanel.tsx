import { useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Props {
  novelId: number;
  novelName: string;
}

/**
 * 保存面板（Phase 3.8）。
 *
 * 当前实现：导出 markdown 文件（包含作品名 + 大纲 + 人物卡）。
 * 灵感库保存由各 step（keyword/plot）自动完成；这里只暴露"导出 md"。
 */
export default function SavePanel({ novelId, novelName }: Props) {
  const [busy, setBusy] = useState(false);

  const handleExport = async () => {
    setBusy(true);
    try {
      await novelsApi.exportMarkdown(novelId, novelName);
      toast.success(`已导出：${novelName}.md`, {
        description: "包含作品信息 + 大纲 + 所有人物卡",
      });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">保存 / 导出</CardTitle>
        <CardDescription>
          灵感园的关键词 / 剧情 / 大纲 / 人物卡都已自动入库。
          这里可以一键导出完整快照为 markdown。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border border-dashed border-neutral-300 dark:border-neutral-700 px-3 py-2 text-xs space-y-1">
          <div>
            <span className="text-neutral-500">当前作品：</span>
            <span className="font-medium">{novelName}</span>
            <span className="ml-2 text-[10px] text-neutral-400 font-mono">
              #{novelId}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleExport} disabled={busy}>
            {busy ? "导出中..." : "导出 markdown"}
          </Button>
        </div>
        <p className="text-[10px] text-neutral-500">
          文件格式：作品名 + 元信息 + 大纲（按类型分别渲染）+ 人物卡（按角色排序）。
        </p>
      </CardContent>
    </Card>
  );
}
