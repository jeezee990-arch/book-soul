import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { charactersApi } from "@/api/characters";
import { ApiError } from "@/api";
import type { Character } from "@/lib/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import CharacterCard from "@/components/CharacterCard";
import CreateCharacterDialog from "@/components/CreateCharacterDialog";

interface Props {
  novelId: number;
  /** 用作自动生成输入的大纲结构（无则隐藏"自动生成"按钮） */
  outline: Record<string, unknown> | null;
  genre: string;
}

const ROLES = ["主角", "主角团", "反派", "正派", "队友", "其他"] as const;
type Role = (typeof ROLES)[number];

export default function CharacterManager({ novelId, outline, genre }: Props) {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await charactersApi.list(novelId);
      setCharacters(list);
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("加载人物失败", { description: msg });
    } finally {
      setLoading(false);
    }
  }, [novelId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAutoGenerate = useCallback(async () => {
    if (!outline) {
      toast.info("需要先有大纲才能自动生成");
      return;
    }
    if (
      !confirm(
        "自动生成会调用 LLM 抽取人物并生成完整卡（可能需要 10-30 秒）。已有的人物不会被替换。继续？",
      )
    ) {
      return;
    }
    setGenerating(true);
    try {
      const resp = await charactersApi.generateFromOutline(novelId, {
        outline,
        genre,
      });
      toast.success(`已自动生成 ${resp.characters.length} 个人物卡`);
      load();
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("自动生成失败", { description: msg });
    } finally {
      setGenerating(false);
    }
  }, [outline, novelId, genre, load]);

  // 按角色分组
  const grouped = useMemo(() => {
    const g: Record<Role, Character[]> = {
      主角: [],
      主角团: [],
      反派: [],
      正派: [],
      队友: [],
      其他: [],
    };
    for (const c of characters) {
      const r = (ROLES as readonly string[]).includes(c.role)
        ? (c.role as Role)
        : "其他";
      g[r].push(c);
    }
    return g;
  }, [characters]);

  const totalActive = characters.filter((c) => c.is_active).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">人物卡管理</CardTitle>
            <CardDescription>
              共 {characters.length} 人（活跃 {totalActive}） · 按角色分组
            </CardDescription>
          </div>
          <div className="flex shrink-0 gap-1.5">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setCreateOpen(true)}
            >
              手动添加
            </Button>
            <Button
              size="sm"
              onClick={handleAutoGenerate}
              disabled={generating || !outline}
              title={!outline ? "需要先有大纲" : "调 LLM 抽取+生成卡"}
            >
              {generating ? "生成中..." : "从大纲自动生成"}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <p className="text-xs text-neutral-500">加载中...</p>
        ) : characters.length === 0 ? (
          <div className="rounded-md border border-dashed border-neutral-300 dark:border-neutral-700 p-6 text-center space-y-2">
            <p className="text-sm text-neutral-500">还没有人物</p>
            <p className="text-xs text-neutral-400">
              {outline
                ? '点"从大纲自动生成"调 LLM 一键生成，或"手动添加"自己写'
                : '先完成"大纲生成"步骤拿到大纲，再回来自动生成；或"手动添加"先建一两个'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {ROLES.map((role) => {
              const list = grouped[role];
              if (list.length === 0) return null;
              return (
                <div key={role} className="space-y-2">
                  <div className="flex items-baseline gap-2">
                    <h3 className="text-sm font-medium">{role}</h3>
                    <span className="text-[10px] text-neutral-400">
                      {list.length} 人
                    </span>
                  </div>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {list.map((c) => (
                      <CharacterCard key={c.id} character={c} onChanged={load} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      <CreateCharacterDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        novelId={novelId}
        onCreated={load}
      />
    </Card>
  );
}
