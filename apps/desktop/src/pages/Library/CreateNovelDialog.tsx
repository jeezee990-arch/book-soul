/**
 * 新建作品对话框（素材库 · 作品 Tab）。
 *
 * 旧实现里「新建作品」是一个死按钮（点开只弹「敬请期待」toast），
 * 但后端 POST /novels 早就绪了 —— 这里接上它。
 *
 * 2026-10-30 补：重名检测。
 * 素材库里不能有两本同名作品（用户靠名字区分书）→ 输入时**当场提示**，
 * 并给一键改名按钮，别等提交了才报错（后端会返 409）。
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import { GENRE_PRIORITY } from "@/config/genres";
import { duplicateHint, uniqueName } from "@/lib/novel-name";
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
import { cn } from "@/lib/utils";
import type { Novel } from "@/lib/types";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (novel: Novel) => void;
}

export default function CreateNovelDialog({
  open,
  onOpenChange,
  onCreated,
}: Props) {
  const [name, setName] = useState("");
  const [genre, setGenre] = useState(GENRE_PRIORITY[0].name);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  /** 素材库里已有的作品名（用来查重） */
  const [existingNames, setExistingNames] = useState<string[]>([]);

  useEffect(() => {
    if (open) {
      setName("");
      setGenre(GENRE_PRIORITY[0].name);
      setDescription("");
      // 拉一次现有作品名用于查重（失败不阻塞创建）
      void novelsApi
        .list()
        .then((list) => setExistingNames(list.map((n) => n.name)))
        .catch(() => setExistingNames([]));
    }
  }, [open]);

  /** 重名提示（为空 = 不重名）。 */
  const hint = useMemo(
    () => duplicateHint(name, existingNames),
    [name, existingNames],
  );
  /** 自动避让后的名字（「用这个」按钮填它）。 */
  const suggested = useMemo(
    () => (name.trim() ? uniqueName(name, existingNames) : ""),
    [name, existingNames],
  );

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) {
      toast.error("请输入作品名");
      return;
    }
    setBusy(true);
    try {
      const novel = await novelsApi.create({
        name: trimmed,
        genre,
        style: null,
        description: description.trim() || null,
        status: "draft",
        outline_mode: null,
        file_path: null,
        imported: false,
        read_only: false,
      });
      toast.success("作品已创建", { description: novel.name });
      onCreated(novel);
      onOpenChange(false);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        toast.error("已有同名作品", {
          description: `素材库里已经有《${trimmed}》，换个名字吧`,
        });
        return;
      }
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("创建失败", { description: msg });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建作品</DialogTitle>
          <DialogDescription>
            先建一个空壳，之后可以在「开新书」里让 AI 生成大纲与人物卡，
            也可以直接手写章节。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-xs text-neutral-500">作品名 *</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：剑起青云"
              maxLength={120}
              autoFocus
            />
            {hint ? (
              <div className="flex items-center gap-2 text-[11.5px] text-amber-600 dark:text-amber-400">
                <span className="flex-1">{hint}</span>
                {suggested !== name.trim() ? (
                  <button
                    type="button"
                    onClick={() => setName(suggested)}
                    className="shrink-0 rounded-md border border-amber-500/40 px-1.5 py-0.5 transition-colors hover:bg-amber-500/10"
                  >
                    用「{suggested}」
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-neutral-500">题材</label>
            <div className="flex flex-wrap gap-1.5">
              {GENRE_PRIORITY.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => setGenre(g.name)}
                  className={cn(
                    "h-8 rounded-lg border px-3 text-[12px] transition-colors",
                    genre === g.name
                      ? "border-indigo-500 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
                      : "border-neutral-200 text-neutral-600 hover:border-neutral-300 dark:border-neutral-800 dark:text-neutral-400",
                  )}
                >
                  {g.emoji} {g.name}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs text-neutral-500">简介（可选）</label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="一句话说清这本书讲什么"
              rows={3}
              maxLength={2000}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            取消
          </Button>
          <Button onClick={() => void submit()} disabled={busy}>
            {busy ? "创建中…" : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
