import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { chaptersApi, type ChapterCreate } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Chapter } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  novelId: number | null;
  /** 已存在章节，用于自动算下一个 chapter_number */
  existing: Chapter[];
  onCreated: (chapter: Chapter) => void;
}

/** 新建章节对话框（Phase 4.1）。 */
export default function CreateChapterDialog({
  open,
  onOpenChange,
  novelId,
  existing,
  onCreated,
}: Props) {
  const [title, setTitle] = useState("");
  const [outline, setOutline] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle("");
      setOutline("");
    }
  }, [open]);

  const nextNumber = existing.length > 0
    ? Math.max(...existing.map((c) => c.chapter_number)) + 1
    : 1;

  async function handleSubmit() {
    if (novelId === null) return;
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast.error("请输入章节标题");
      return;
    }
    const payload: ChapterCreate = {
      novel_id: novelId,
      chapter_number: nextNumber,
      title: trimmedTitle,
      outline: outline.trim() || null,
      status: "outline",
    };
    setSubmitting(true);
    try {
      const chapter = await chaptersApi.create(payload);
      toast.success("章节已创建", { description: chapter.title ?? undefined });
      onCreated(chapter);
      onOpenChange(false);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("创建失败", { description: msg });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建章节</DialogTitle>
          <DialogDescription>
            将在作品下创建第 {nextNumber} 章。先填标题和大纲，后续可在创作页生成内容。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-xs text-neutral-500">标题</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：韩立入七玄门"
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-neutral-500">大纲/概要（可选）</label>
            <Textarea
              value={outline}
              onChange={(e) => setOutline(e.target.value)}
              placeholder="本章主要发生什么？"
              rows={4}
              maxLength={10_000}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "创建中…" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
