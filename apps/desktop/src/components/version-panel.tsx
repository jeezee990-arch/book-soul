import { useEffect, useState } from "react";
import { toast } from "sonner";
import { History, RotateCcw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { chaptersApi } from "@/api/chapters";
import { versionsApi } from "@/api/versions";
import { ApiError } from "@/api";
import type { Chapter, ChapterVersion } from "@/lib/types";
import { cn } from "@/lib/utils";
import DiffViewer from "@/components/DiffViewer";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chapter: Chapter | null;
  onRollback: (newVersion: ChapterVersion) => void;
}

const TRIGGER_LABEL: Record<string, string> = {
  user_create: "创建",
  user_edit: "手动编辑",
  rewrite: "AI 重写",
  llm_generate: "LLM 生成",
  imported: "导入",
  rollback: "回滚",
};

const TRIGGER_TONE: Record<string, string> = {
  user_create: "bg-neutral-100 text-neutral-600",
  user_edit: "bg-blue-100 text-blue-700",
  rewrite: "bg-amber-100 text-amber-700",
  llm_generate: "bg-emerald-100 text-emerald-700",
  imported: "bg-purple-100 text-purple-700",
  rollback: "bg-rose-100 text-rose-700",
};

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

/** 章节版本历史面板（Phase 4.6）。
 *
 * Dialog 内：左侧版本列表（按时间倒序），右侧 diff + 回滚按钮。
 */
export default function VersionPanel({ open, onOpenChange, chapter, onRollback }: Props) {
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [diffText, setDiffText] = useState<string>("");
  const [stats, setStats] = useState<{ added: number; removed: number } | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);

  // 打开时拉版本列表
  useEffect(() => {
    if (!open || !chapter) return;
    let cancelled = false;
    setLoading(true);
    setSelectedId(null);
    setDiffText("");
    setStats(null);
    chaptersApi
      .listVersions(chapter.id)
      .then((data) => {
        if (!cancelled) {
          setVersions(data);
          if (data.length > 0) setSelectedId(data[0].id);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) {
          toast.error("加载版本失败", { description: msg });
          setVersions([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, chapter]);

  // 选中版本时拉 diff
  useEffect(() => {
    if (!open || !chapter || selectedId === null) return;
    let cancelled = false;
    setDiffLoading(true);
    setDiffText("");
    setStats(null);
    versionsApi
      .diff(chapter.id, selectedId)
      .then((resp) => {
        if (!cancelled) {
          setDiffText(resp.diff);
          setStats(resp.stats);
        }
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) toast.error("加载 diff 失败", { description: msg });
      })
      .finally(() => {
        if (!cancelled) setDiffLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, chapter, open]);

  async function handleRollback() {
    if (!chapter || selectedId === null) return;
    if (!confirm("确认回滚到该版本？将生成一条新版本（parent=当前最新），原历史保留。")) return;
    setRollingBack(true);
    try {
      const resp = await versionsApi.rollback(chapter.id, selectedId);
      toast.success("已回滚", { description: `新建版本 #${resp.new_version.id}` });
      onRollback(resp.new_version);
      onOpenChange(false);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("回滚失败", { description: msg });
    } finally {
      setRollingBack(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            版本历史
          </DialogTitle>
          <DialogDescription>
            {chapter ? `第 ${chapter.chapter_number} 章 · ${chapter.title ?? "（未命名）"}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-[260px_1fr] gap-4 min-h-[400px]">
          {/* 左：版本列表 */}
          <div className="border border-neutral-200 dark:border-neutral-800 rounded-md overflow-hidden">
            <div className="px-3 py-2 bg-neutral-50 dark:bg-neutral-900/50 text-xs font-medium text-neutral-600 dark:text-neutral-400 border-b border-neutral-200 dark:border-neutral-800">
              版本 · {versions.length}
            </div>
            <div className="max-h-[480px] overflow-y-auto">
              {loading && (
                <p className="p-3 text-xs text-neutral-400">加载中…</p>
              )}
              {!loading && versions.length === 0 && (
                <p className="p-3 text-xs text-neutral-400">暂无版本</p>
              )}
              {versions.map((v) => (
                <button
                  key={v.id}
                  onClick={() => setSelectedId(v.id)}
                  className={cn(
                    "w-full text-left px-3 py-2 text-xs border-b border-neutral-100 dark:border-neutral-800 transition-colors",
                    v.id === selectedId
                      ? "bg-neutral-100 dark:bg-neutral-800"
                      : "hover:bg-neutral-50 dark:hover:bg-neutral-900/50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px]",
                        TRIGGER_TONE[v.trigger] ?? "bg-neutral-100 text-neutral-600",
                      )}
                    >
                      {TRIGGER_LABEL[v.trigger] ?? v.trigger}
                    </span>
                    <span className="text-neutral-500">#{v.id}</span>
                  </div>
                  <div className="mt-1 text-neutral-500">{formatTime(v.created_at)}</div>
                  <div className="text-neutral-400">{v.word_count.toLocaleString()} 字</div>
                </button>
              ))}
            </div>
          </div>

          {/* 右：diff + 回滚 */}
          <div className="space-y-3">
            {diffLoading && (
              <p className="text-xs text-neutral-400">加载 diff…</p>
            )}
            {!diffLoading && !diffText && (
              <p className="text-xs text-neutral-400 italic">
                {selectedId === null
                  ? "选择左侧版本查看 diff"
                  : "该版本与 parent 无差异（可能是初始版本）"}
              </p>
            )}
            {diffText && (
              <>
                {stats && (stats.added > 0 || stats.removed > 0) && (
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-emerald-700 dark:text-emerald-300">
                      +{stats.added}
                    </span>
                    <span className="text-rose-700 dark:text-rose-300">
                      -{stats.removed}
                    </span>
                  </div>
                )}
                <DiffViewer diff={diffText} maxHeight={420} />
              </>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
          <Button
            onClick={handleRollback}
            disabled={!selectedId || diffLoading || rollingBack}
          >
            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
            {rollingBack ? "回滚中…" : "回滚到该版本"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
