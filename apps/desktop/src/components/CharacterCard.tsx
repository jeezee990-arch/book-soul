import { useState } from "react";
import { toast } from "sonner";
import { charactersApi, type CharacterUpdate } from "@/api/characters";
import { ApiError } from "@/api";
import type { Character } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import CharacterGrowthDialog from "@/components/CharacterGrowthDialog";

interface Props {
  character: Character;
  onChanged: () => void;
}

const ROLE_COLOR: Record<string, string> = {
  主角: "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-100",
  主角团: "bg-sky-100 text-sky-900 dark:bg-sky-900/30 dark:text-sky-100",
  反派: "bg-rose-100 text-rose-900 dark:bg-rose-900/30 dark:text-rose-100",
  正派:
    "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-100",
  队友: "bg-violet-100 text-violet-900 dark:bg-violet-900/30 dark:text-violet-100",
  其他: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200",
};

const FIELDS = [
  { key: "basic_info", label: "基本信息" },
  { key: "personality", label: "性格" },
  { key: "habits", label: "习惯" },
  { key: "thinking", label: "思维方式" },
  { key: "relationships", label: "人物关系" },
  { key: "growth_arc", label: "成长弧线" },
] as const;

export default function CharacterCard({ character, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<CharacterUpdate>({});
  const [growthOpen, setGrowthOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const roleCls = ROLE_COLOR[character.role] ?? ROLE_COLOR["其他"];

  const startEdit = () => {
    setDraft({
      name: character.name,
      role: character.role,
      basic_info: character.basic_info,
      personality: character.personality,
      habits: character.habits,
      thinking: character.thinking,
      relationships: character.relationships,
      growth_arc: character.growth_arc,
      is_active: character.is_active,
    });
    setEditing(true);
  };

  const handleSave = async () => {
    setBusy(true);
    try {
      await charactersApi.update(character.id, draft);
      toast.success(`已保存：${draft.name ?? character.name}`);
      setEditing(false);
      onChanged();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("保存失败", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`确定删除人物「${character.name}」？`)) return;
    setBusy(true);
    try {
      await charactersApi.remove(character.id);
      toast.success(`已删除：${character.name}`);
      onChanged();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("删除失败", { description: msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={[
        "rounded-md border p-3 space-y-2",
        character.is_active
          ? "border-neutral-200 dark:border-neutral-800"
          : "border-dashed border-neutral-300 dark:border-neutral-700 opacity-60",
      ].join(" ")}
    >
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {editing ? (
            <Input
              value={draft.name ?? ""}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className="text-sm font-medium"
            />
          ) : (
            <div className="text-sm font-medium truncate">
              {character.name}
              {!character.is_active && (
                <span className="ml-1 text-[10px] text-neutral-500">
                  （退场）
                </span>
              )}
            </div>
          )}
          <div className="mt-1 flex items-center gap-1.5">
            {editing ? (
              <select
                value={draft.role ?? "其他"}
                onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                className="rounded-md border border-neutral-200 dark:border-neutral-800 bg-transparent px-1.5 py-0.5 text-[11px]"
              >
                {["主角", "主角团", "反派", "正派", "队友", "其他"].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            ) : (
              <span
                className={`rounded-md px-1.5 py-0.5 text-[10px] ${roleCls}`}
              >
                {character.role}
              </span>
            )}
            <span className="text-[10px] text-neutral-400 font-mono">
              #{character.id}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {editing ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditing(false)}
                disabled={busy}
              >
                取消
              </Button>
              <Button size="sm" onClick={handleSave} disabled={busy}>
                {busy ? "保存中..." : "保存"}
              </Button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                variant="ghost"
                onClick={startEdit}
                disabled={busy}
              >
                编辑
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setGrowthOpen(true)}
                disabled={busy}
              >
                记录变化
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleDelete}
                disabled={busy}
                className="text-destructive hover:text-destructive"
              >
                删除
              </Button>
            </>
          )}
        </div>
      </div>

      {/* fields */}
      <div className="space-y-1.5">
        {FIELDS.map((f) => (
          <div key={f.key} className="text-xs">
            <span className="text-neutral-500 mr-1">{f.label}：</span>
            {editing ? (
              <Textarea
                value={(draft[f.key] as string | null) ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, [f.key]: e.target.value })
                }
                rows={2}
                className="mt-1 text-xs"
              />
            ) : (
              <span className="whitespace-pre-wrap">
                {character[f.key] || (
                  <span className="text-neutral-400">（未填）</span>
                )}
              </span>
            )}
          </div>
        ))}
      </div>

      <CharacterGrowthDialog
        open={growthOpen}
        onOpenChange={setGrowthOpen}
        characterId={character.id}
        characterName={character.name}
        onRecorded={onChanged}
      />
    </div>
  );
}
