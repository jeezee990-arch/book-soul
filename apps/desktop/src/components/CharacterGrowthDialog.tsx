import { useState } from "react";
import { toast } from "sonner";
import { charactersApi } from "@/api/characters";
import { ApiError } from "@/api";
import type { CharacterGrowthEvent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  characterId: number;
  characterName: string;
  onRecorded: () => void;
}

export default function CharacterGrowthDialog({
  open,
  onOpenChange,
  characterId,
  characterName,
  onRecorded,
}: Props) {
  const [growth, setGrowth] = useState<CharacterGrowthEvent>({ event: "" });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!growth.event.trim()) {
      toast.info("请输入触发事件描述");
      return;
    }
    setBusy(true);
    try {
      const payload: CharacterGrowthEvent = {
        event: growth.event.trim(),
        new_personality: growth.new_personality?.trim() || undefined,
        new_habits: growth.new_habits?.trim() || undefined,
        new_thinking: growth.new_thinking?.trim() || undefined,
        new_relationships: growth.new_relationships?.trim() || undefined,
      };
      await charactersApi.recordGrowth(characterId, payload);
      toast.success("已记录性格变化 + 新版本");
      onOpenChange(false);
      setGrowth({ event: "" });
      onRecorded();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("记录失败", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>记录性格变化</DialogTitle>
          <DialogDescription>
            为「{characterName}」记录一次事件，自动追加到 growth_arc 并创建新版本。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-neutral-500">事件描述 *</label>
            <Input
              value={growth.event}
              onChange={(e) =>
                setGrowth({ ...growth, event: e.target.value })
              }
              placeholder="如：经历师门变故后性格大变"
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500">
              新性格（留空不改）
            </label>
            <Textarea
              rows={2}
              value={growth.new_personality ?? ""}
              onChange={(e) =>
                setGrowth({ ...growth, new_personality: e.target.value })
              }
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500">新习惯</label>
            <Textarea
              rows={2}
              value={growth.new_habits ?? ""}
              onChange={(e) =>
                setGrowth({ ...growth, new_habits: e.target.value })
              }
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500">新思维方式</label>
            <Textarea
              rows={2}
              value={growth.new_thinking ?? ""}
              onChange={(e) =>
                setGrowth({ ...growth, new_thinking: e.target.value })
              }
            />
          </div>
          <div>
            <label className="text-xs text-neutral-500">新人物关系</label>
            <Textarea
              rows={2}
              value={growth.new_relationships ?? ""}
              onChange={(e) =>
                setGrowth({ ...growth, new_relationships: e.target.value })
              }
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
          <Button onClick={submit} disabled={busy}>
            {busy ? "提交中..." : "记录"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
