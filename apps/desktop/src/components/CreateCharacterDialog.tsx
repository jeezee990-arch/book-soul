import { useEffect, useState } from "react";
import { toast } from "sonner";
import { charactersApi, type CharacterCreate } from "@/api/characters";
import { ApiError } from "@/api";
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

const ROLES = ["主角", "主角团", "反派", "正派", "队友", "其他"] as const;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  novelId: number;
  onCreated: () => void;
}

export default function CreateCharacterDialog({
  open,
  onOpenChange,
  novelId,
  onCreated,
}: Props) {
  const [draft, setDraft] = useState<CharacterCreate>({
    novel_id: novelId,
    name: "",
    role: "其他",
    basic_info: null,
    personality: null,
    habits: null,
    thinking: null,
    relationships: null,
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setDraft({
        novel_id: novelId,
        name: "",
        role: "其他",
        basic_info: null,
        personality: null,
        habits: null,
        thinking: null,
        relationships: null,
      });
    }
  }, [open, novelId]);

  const submit = async () => {
    if (!draft.name.trim()) {
      toast.info("请输入人物名");
      return;
    }
    setBusy(true);
    try {
      await charactersApi.create({
        ...draft,
        name: draft.name.trim(),
      });
      toast.success(`已添加：${draft.name.trim()}`);
      onOpenChange(false);
      onCreated();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("添加失败", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>手动添加人物</DialogTitle>
          <DialogDescription>
            必填姓名 + 角色定位，其他字段可后补或编辑。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <label className="text-xs text-neutral-500">姓名 *</label>
              <Input
                value={draft.name}
                onChange={(e) =>
                  setDraft({ ...draft, name: e.target.value })
                }
              />
            </div>
            <div>
              <label className="text-xs text-neutral-500">角色</label>
              <select
                value={draft.role}
                onChange={(e) =>
                  setDraft({ ...draft, role: e.target.value })
                }
                className="w-full rounded-md border border-neutral-200 dark:border-neutral-800 bg-transparent px-2 py-1.5 text-xs"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {(
            [
              ["basic_info", "基本信息"],
              ["personality", "性格"],
              ["habits", "习惯"],
              ["thinking", "思维方式"],
              ["relationships", "人物关系"],
            ] as const
          ).map(([k, label]) => (
            <div key={k}>
              <label className="text-xs text-neutral-500">{label}</label>
              <Textarea
                rows={2}
                value={draft[k] ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, [k]: e.target.value || null })
                }
              />
            </div>
          ))}
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
            {busy ? "添加中..." : "添加"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
