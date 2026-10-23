/**
 * 人物 Tab：本书人物卡（读 + 改 + 增）。
 *
 * 补上最大的功能断链：以前人物卡生成后前端**完全没有界面**，
 * `CharacterCard` / `CreateCharacterDialog` 组件写好了却没有任何页面引用。
 * 这里把两个组件接上 —— 编辑、记录成长变化、删除、新增全部可用。
 */

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, Plus, Users } from "lucide-react";
import { charactersApi } from "@/api/characters";
import { ApiError } from "@/api";
import type { Character, Novel } from "@/lib/types";
import CharacterCard from "@/components/CharacterCard";
import CreateCharacterDialog from "@/components/CreateCharacterDialog";
import { HintBar, SectionLabel } from "../ui";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** 角色 → 徽标配色。 */
const ROLE_TONE: Record<string, string> = {
  主角: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  主角团: "bg-sky-500/15 text-sky-600 dark:text-sky-300",
  反派: "bg-rose-500/15 text-rose-600 dark:text-rose-300",
  正派: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
  队友: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
  其他: "bg-neutral-500/15 text-neutral-500 dark:text-neutral-400",
};

/** 头像底色：按名字散列，保证同一人颜色稳定。 */
function avatarTone(name: string): string {
  const tones = [
    "linear-gradient(150deg,#4f46e5,#6366f1)",
    "linear-gradient(150deg,#db2777,#8b5cf6)",
    "linear-gradient(150deg,#dc2626,#f59e0b)",
    "linear-gradient(150deg,#0ea5e9,#14b8a6)",
    "linear-gradient(150deg,#10b981,#84cc16)",
  ];
  let h = 0;
  for (let i = 0; i < name.length; i += 1) h = (h + name.charCodeAt(i)) % 997;
  return tones[h % tones.length];
}

interface Props {
  novel: Novel | null;
}

export default function CharacterTab({ novel }: Props) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async (novelId: number) => {
    setLoading(true);
    setError(null);
    try {
      const list = await charactersApi.list(novelId);
      setCharacters(list);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!novel) {
      setCharacters([]);
      return;
    }
    void load(novel.id);
  }, [novel, load]);

  if (!novel) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        先在顶栏选一本作品
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <div className="min-h-0 flex-1 px-3.5 py-3.5">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h4 className="text-[12.5px] font-semibold">
            本书人物
            {characters.length > 0 ? ` · ${characters.length}` : ""}
          </h4>
          <Button
            size="sm"
            variant="outline"
            className="h-7 shrink-0 px-2.5 text-[11.5px]"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            新增
          </Button>
        </div>

        {error ? <HintBar tone="error">加载失败：{error}</HintBar> : null}

        {loading ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800/60"
              />
            ))}
          </div>
        ) : null}

        {!loading && characters.length === 0 && !error ? (
          <div className="py-8 text-center">
            <Users className="mx-auto mb-2 h-6 w-6 text-neutral-300 dark:text-neutral-700" />
            <p className="text-[12px] text-neutral-400">
              这本书还没有人物卡
            </p>
            <p className="mt-1 text-[11px] text-neutral-400">
              可以去「开新书」让 AI 生成，或点上方「新增」手动添加
            </p>
          </div>
        ) : null}

        {characters.length > 0 ? (
          <>
            <SectionLabel>全部角色</SectionLabel>
            <div className="space-y-1.5">
              {characters.map((c) => {
                const open = expandedId === c.id;
                return (
                  <div
                    key={c.id}
                    className={cn(
                      "overflow-hidden rounded-lg border transition-colors",
                      open
                        ? "border-violet-500/50"
                        : "border-neutral-200 dark:border-neutral-800",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedId(open ? null : c.id)}
                      className="flex w-full items-center gap-2.5 bg-neutral-50 px-2.5 py-2 text-left transition-colors hover:bg-neutral-100 dark:bg-neutral-800/40 dark:hover:bg-neutral-800/70"
                    >
                      <span
                        className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-[13px] font-semibold text-white"
                        style={{ background: avatarTone(c.name) }}
                      >
                        {c.name.slice(0, 1)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1.5">
                          <span className="truncate text-[12.5px] font-semibold">
                            {c.name}
                          </span>
                          {!c.is_active ? (
                            <span className="text-[10px] text-neutral-400">
                              （退场）
                            </span>
                          ) : null}
                        </span>
                        <span
                          className={cn(
                            "mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px]",
                            ROLE_TONE[c.role] ?? ROLE_TONE["其他"],
                          )}
                        >
                          {c.role}
                        </span>
                      </span>
                      <ChevronDown
                        className={cn(
                          "h-3.5 w-3.5 shrink-0 text-neutral-400 transition-transform",
                          open && "rotate-180",
                        )}
                      />
                    </button>
                    {open ? (
                      <div className="border-t border-neutral-200 p-2.5 dark:border-neutral-800">
                        <CharacterCard
                          character={c}
                          onChanged={() => void load(novel.id)}
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            <div className="mt-3">
              <HintBar tone="ai">
                生成正文时只注入「本章出场」的人物卡，避免上下文被无关角色撑满。
              </HintBar>
            </div>
          </>
        ) : null}
      </div>

      <CreateCharacterDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        novelId={novel.id}
        onCreated={() => void load(novel.id)}
      />
    </div>
  );
}
