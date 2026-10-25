/**
 * 大纲 Tab：结构化渲染 + 可编辑 + 一键拆章。
 *
 * 旧实现里大纲只以 `JSON.stringify(structure)` 显示在作品详情抽屉里，
 * 作者看到的是裸 JSON，既读不懂也改不了。
 * 这里按后端 schema（complete: volumes→chapters→key_events）结构化展示，
 * 并支持：
 * - 编辑章节标题 / 概要 / 关键事件（PATCH 落库）
 * - 把大纲里的章节一键创建成正文章节（打通"大纲 → 正文"）
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Loader2, Pencil, Plus, ScrollText, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { outlinesApi } from "@/api/outlines";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import {
  detectStreamFailure,
  parseOutlineStreamEvent,
  readNdjsonStream,
} from "@/api/streams";
import type { Chapter, Novel, Outline } from "@/lib/types";
import { HintBar, SectionLabel } from "../ui";
import { Button } from "@/components/ui/button";

// ===== structure 类型（对齐 server/src/schemas/outline.py）=====

interface ChapterNode {
  title: string;
  summary?: string | null;
  key_events?: string[];
}

interface VolumeNode {
  name: string;
  summary?: string | null;
  chapters?: ChapterNode[];
}

interface CompleteStructure {
  volumes?: VolumeNode[];
  overall_theme?: string | null;
}

interface FreedomStructure {
  summary?: string;
  key_beats?: string[];
  themes?: string[];
}

interface Props {
  novel: Novel | null;
  /** 章节版本变化时触发刷新（拆章后要重画） */
  versionTick: number;
}

export default function OutlineTab({ novel, versionTick }: Props) {
  const [outlines, setOutlines] = useState<Outline[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async (novelId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [outs, chs] = await Promise.all([
        outlinesApi.list(novelId),
        chaptersApi.list(novelId),
      ]);
      setOutlines(outs);
      setChapters(chs);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!novel) {
      setOutlines([]);
      setChapters([]);
      return;
    }
    void load(novel.id);
  }, [novel, load, versionTick]);

  /** 大纲里还没建过正文章节的条目 */
  const pending = useMemo(() => {
    const existing = new Set(
      chapters.map((c) => (c.title ?? "").trim()).filter(Boolean),
    );
    const items: { volume: string; node: ChapterNode }[] = [];
    for (const o of outlines) {
      if (o.outline_type !== "complete") continue;
      const s = o.structure as CompleteStructure;
      for (const v of s.volumes ?? []) {
        for (const node of v.chapters ?? []) {
          if (!existing.has(node.title.trim())) {
            items.push({ volume: v.name, node });
          }
        }
      }
    }
    return items;
  }, [outlines, chapters]);

  /** 一键把待写的大纲章节创建成正文章节 */
  async function createChapters(targets: { volume: string; node: ChapterNode }[]) {
    if (!novel || targets.length === 0) return;
    setCreating(true);
    try {
      let nextNo = chapters.length
        ? Math.max(...chapters.map((c) => c.chapter_number)) + 1
        : 1;
      const created: Chapter[] = [];
      for (const t of targets) {
        const summary = [
          t.node.summary,
          ...(t.node.key_events ?? []).map((e) => `· ${e}`),
        ]
          .filter(Boolean)
          .join("\n");
        const ch = await chaptersApi.create({
          novel_id: novel.id,
          chapter_number: nextNo,
          title: t.node.title,
          outline: summary || null,
          status: "outline",
        });
        created.push(ch);
        nextNo += 1;
      }
      toast.success(`已创建 ${created.length} 个章节`, {
        description: "已按大纲建好，去左边章节树开始写",
      });
      await load(novel.id);
    } catch (e: unknown) {
      toast.error("创建章节失败", {
        description: e instanceof ApiError ? e.message : String(e),
      });
    } finally {
      setCreating(false);
    }
  }

  if (!novel) {
    return (
      <div className="px-3.5 py-6 text-center text-[12px] text-neutral-400">
        先在顶栏选一本作品
      </div>
    );
  }

  if (loading && outlines.length === 0) {
    return (
      <div className="space-y-2 px-3.5 py-3.5">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800/60"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="px-3.5 py-3.5">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-[12.5px] font-semibold">
          大纲
          {outlines.length > 0 ? ` · ${outlines.length} 份` : ""}
        </h4>
        {pending.length > 0 ? (
          <Button
            size="sm"
            className="h-7 shrink-0 bg-violet-600 px-2.5 text-[11.5px] text-white hover:bg-violet-700"
            disabled={creating}
            onClick={() => void createChapters(pending)}
          >
            {creating ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="mr-1.5 h-3.5 w-3.5" />
            )}
            创建 {pending.length} 个待写章节
          </Button>
        ) : null}
      </div>

      {error ? <HintBar tone="error">加载失败：{error}</HintBar> : null}

      {!loading && outlines.length === 0 && !error ? (
        <div className="py-8 text-center">
          <ScrollText className="mx-auto mb-2 h-6 w-6 text-neutral-300 dark:text-neutral-700" />
          <p className="text-[12px] text-neutral-400">这本书还没有大纲</p>
          <p className="mt-1 text-[11px] text-neutral-400">
            去「开新书」时 AI 会自动生成一份
          </p>
        </div>
      ) : null}

      {outlines.map((o) => (
        <OutlineBlock
          key={o.id}
          outline={o}
          novelId={novel.id}
          editingKey={editing}
          onEditingChange={setEditing}
          onSaved={() => void load(novel.id)}
          onCreateChapters={(targets) => void createChapters(targets)}
        />
      ))}
    </div>
  );
}

// ===== 单份大纲 =====

function OutlineBlock({
  outline,
  novelId,
  editingKey,
  onEditingChange,
  onSaved,
  onCreateChapters,
}: {
  outline: Outline;
  novelId: number;
  editingKey: string | null;
  onEditingChange: (key: string | null) => void;
  onSaved: () => void;
  onCreateChapters: (targets: { volume: string; node: ChapterNode }[]) => void;
}) {
  if (outline.outline_type === "freedom") {
    const s = outline.structure as FreedomStructure;
    return (
      <div className="mb-3 rounded-xl border border-neutral-200 p-2.5 dark:border-neutral-800">
        <SectionLabel>创作型大纲</SectionLabel>
        {s.summary ? (
          <p className="mb-2 font-serif text-[12px] leading-relaxed text-neutral-600 dark:text-neutral-400">
            {s.summary}
          </p>
        ) : null}
        {s.key_beats && s.key_beats.length > 0 ? (
          <ul className="list-disc space-y-0.5 pl-4">
            {s.key_beats.map((b, i) => (
              <li
                key={i}
                className="text-[11.5px] text-neutral-500 dark:text-neutral-400"
              >
                {b}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  const s = outline.structure as CompleteStructure;
  const volumes = s.volumes ?? [];

  return (
    <div className="mb-3">
      {s.overall_theme ? (
        <HintBar tone="ai">
          <b className="font-semibold">全篇主题</b>：{s.overall_theme}
        </HintBar>
      ) : null}

      {/* AI 辅助续写：接着已有大纲 + 已写章节往下生成 */}
      <ContinuePanel novelId={novelId} outline={outline} onDone={onSaved} />

      {volumes.map((v) => {
        const volKey = `${outline.id}:${v.name}`;
        return (
          <div
            key={volKey}
            className="mt-2.5 overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800"
          >
            <div className="flex items-center gap-2 bg-neutral-100 px-2.5 py-1.5 dark:bg-neutral-800/60">
              <span className="text-[12px] font-semibold">{v.name}</span>
              <span className="ml-auto text-[10.5px] text-neutral-400">
                {v.chapters?.length ?? 0} 章
              </span>
            </div>

            {(v.chapters ?? []).map((node, ci) => {
              const nodeKey = `${volKey}:${ci}`;
              const isEditing = editingKey === nodeKey;
              return (
                <div
                  key={nodeKey}
                  className="border-t border-neutral-200 px-2.5 py-2 dark:border-neutral-800"
                >
                  {isEditing ? (
                    <ChapterEditor
                      node={node}
                      onCancel={() => onEditingChange(null)}
                      onSave={async (next) => {
                        try {
                          const nextVolumes = volumes.map((vv) =>
                            vv.name === v.name
                              ? {
                                  ...vv,
                                  chapters: (vv.chapters ?? []).map((c, i) =>
                                    i === ci ? next : c,
                                  ),
                                }
                              : vv,
                          );
                          await outlinesApi.update(outline.id, novelId, {
                            structure: { ...s, volumes: nextVolumes },
                          });
                          toast.success("大纲已保存");
                          onEditingChange(null);
                          onSaved();
                        } catch (e: unknown) {
                          toast.error("保存失败", {
                            description:
                              e instanceof ApiError ? e.message : String(e),
                          });
                        }
                      }}
                    />
                  ) : (
                    <>
                      <div className="flex items-start gap-1.5">
                        <span className="mt-px font-mono text-[10.5px] text-violet-400">
                          CH{String(ci + 1).padStart(2, "0")}
                        </span>
                        <span className="min-w-0 flex-1 text-[12px] font-medium">
                          {node.title}
                        </span>
                        <button
                          type="button"
                          onClick={() => onEditingChange(nodeKey)}
                          className="shrink-0 rounded p-1 text-neutral-400 transition-colors hover:bg-neutral-200/60 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
                          title="编辑"
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                      </div>
                      {node.summary ? (
                        <p className="mt-1 pl-[46px] text-[11.5px] leading-relaxed text-neutral-500 dark:text-neutral-400">
                          {node.summary}
                        </p>
                      ) : null}
                      {node.key_events && node.key_events.length > 0 ? (
                        <ul className="mt-1 space-y-0.5 pl-[46px]">
                          {node.key_events.map((e, i) => (
                            <li
                              key={i}
                              className="text-[11px] leading-relaxed text-neutral-400"
                            >
                              · {e}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </>
                  )}
                </div>
              );
            })}

            <div className="border-t border-neutral-200 px-2.5 py-1.5 dark:border-neutral-800">
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[10.5px]"
                onClick={() =>
                  onCreateChapters(
                    (v.chapters ?? []).map((node) => ({
                      volume: v.name,
                      node,
                    })),
                  )
                }
              >
                <Plus className="mr-1 h-3 w-3" />
                把本卷章节创建为正文
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ===== AI 辅助续写后续卷 =====

/**
 * 续写面板（2026-10-25 新增）。
 *
 * 对应需求：「半开放式还差一半 —— 后续由作者自行创作或 **AI 辅助生成后续大纲**」。
 *
 * 续写不是重新规划：后端会把**已有大纲 + 已写章节**喂给模型，
 * 让新卷自然接在作者写到的位置后面。
 */
function ContinuePanel({
  novelId,
  outline,
  onDone,
}: {
  novelId: number;
  outline: Outline;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [volumeCount, setVolumeCount] = useState(1);
  /** 每卷章数；空字符串 = 由后端按已有大纲平均值推断 */
  const [cpv, setCpv] = useState("");
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [newVolumes, setNewVolumes] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const start = useCallback(async () => {
    setBusy(true);
    setStatus("正在构思后续卷章…");
    setNewVolumes([]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const req = outlinesApi.continueStream(
      novelId,
      outline.id,
      {
        volume_count: volumeCount,
        chapters_per_volume: cpv.trim() === "" ? undefined : Number(cpv),
        user_extra: extra.trim() || undefined,
      },
      ctrl.signal,
    );
    try {
      for await (const ev of readNdjsonStream(req.url, {
        method: req.method,
        body: req.body,
        signal: ctrl.signal,
      })) {
        // ⚠️ transport 与 server 两类失败都要认（AGENTS.md §4.10）
        const failure = detectStreamFailure(ev);
        if (failure) {
          toast.error("续写失败", { description: failure.message });
          setStatus("");
          return;
        }
        const parsed = parseOutlineStreamEvent(ev);
        if (parsed.kind === "error") {
          toast.error("续写失败", { description: parsed.message });
          setStatus("");
          return;
        }
        if (parsed.kind === "volume_start") {
          setStatus(`正在细化《${parsed.name}》…`);
        } else if (parsed.kind === "volume_done") {
          const name = String(parsed.volume.name ?? "");
          setNewVolumes((s) => (name ? [...s, name] : s));
        } else if (parsed.kind === "volume_error") {
          // 单卷失败不影响其它卷
          setStatus("有一卷没生成出来，其余卷已写入");
        } else if (parsed.kind === "done") {
          toast.success(`已续写 ${parsed.volumeCount ?? newVolumes.length} 卷`, {
            description: "新卷已追加到大纲末尾",
          });
          setStatus("");
          onDone();
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!msg.includes("abort")) {
        toast.error("续写中断", { description: msg });
      }
      setStatus("");
    } finally {
      setBusy(false);
    }
  }, [novelId, outline.id, volumeCount, cpv, extra, onDone, newVolumes.length]);

  if (!open) {
    return (
      <Button
        size="sm"
        variant="ghost"
        className="mt-2 h-7 w-full border border-dashed border-neutral-300 px-2 text-[11.5px] text-neutral-500 dark:border-neutral-700 dark:text-neutral-400"
        onClick={() => setOpen(true)}
      >
        <Sparkles className="mr-1.5 h-3.5 w-3.5" />
        AI 续写后续卷章
      </Button>
    );
  }

  return (
    <div className="mt-2 rounded-xl border border-violet-500/30 bg-violet-500/5 p-2.5">
      <div className="mb-2 flex items-center gap-1.5">
        <Sparkles className="h-3.5 w-3.5 text-violet-400" />
        <span className="text-[12px] font-semibold">AI 续写后续卷章</span>
        <button
          type="button"
          className="ml-auto rounded p-0.5 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
          onClick={() => {
            if (!busy) setOpen(false);
          }}
          title="收起"
        >
          <X className="h-3 w-3" />
        </button>
      </div>

      <p className="mb-2 text-[11px] leading-relaxed text-neutral-400">
        会读取已有大纲和已写章节，新卷接在后面追加，原有内容不动。
      </p>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1 text-[11px] text-neutral-400">
          新增
          <input
            type="number"
            min={1}
            max={5}
            value={volumeCount}
            disabled={busy}
            onChange={(e) =>
              setVolumeCount(Math.max(1, Math.min(5, Number(e.target.value) || 1)))
            }
            className="w-12 rounded-md border border-neutral-200 bg-white px-1.5 py-0.5 text-[11.5px] outline-none dark:border-neutral-700 dark:bg-neutral-900"
          />
          卷
        </label>
        <label className="flex items-center gap-1 text-[11px] text-neutral-400">
          每卷
          <input
            type="number"
            min={1}
            max={100}
            placeholder="沿用"
            value={cpv}
            disabled={busy}
            onChange={(e) => setCpv(e.target.value)}
            className="w-16 rounded-md border border-neutral-200 bg-white px-1.5 py-0.5 text-[11.5px] outline-none placeholder:text-neutral-400 dark:border-neutral-700 dark:bg-neutral-900"
          />
          章
        </label>
      </div>

      <textarea
        value={extra}
        rows={2}
        disabled={busy}
        onChange={(e) => setExtra(e.target.value)}
        placeholder="特别要求（可选）：下一卷主角要面对宿敌的复仇…"
        className="mt-2 w-full resize-none rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-[11.5px] leading-relaxed outline-none placeholder:text-neutral-400 focus:border-violet-400 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900"
      />

      {status ? (
        <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-violet-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          {status}
        </p>
      ) : null}

      {newVolumes.length > 0 ? (
        <ul className="mt-1.5 space-y-0.5">
          {newVolumes.map((v, i) => (
            <li key={`${v}-${i}`} className="flex items-center gap-1 text-[11px] text-emerald-500">
              <Check className="h-3 w-3" />
              {v}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-2.5 flex justify-end gap-1.5">
        <Button
          size="sm"
          variant="ghost"
          className="h-6 px-2 text-[10.5px]"
          disabled={busy}
          onClick={() => setOpen(false)}
        >
          取消
        </Button>
        <Button
          size="sm"
          className="h-6 bg-violet-600 px-2 text-[10.5px] text-white hover:bg-violet-700"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Sparkles className="mr-1 h-3 w-3" />
          )}
          开始续写
        </Button>
      </div>
    </div>
  );
}

// ===== 章节节点编辑表单 =====

function ChapterEditor({
  node,
  onSave,
  onCancel,
}: {
  node: ChapterNode;
  onSave: (next: ChapterNode) => void | Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(node.title);
  const [summary, setSummary] = useState(node.summary ?? "");
  const [events, setEvents] = useState((node.key_events ?? []).join("\n"));
  const [saving, setSaving] = useState(false);

  return (
    <div className="space-y-2">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-[12px] focus:border-indigo-500/60 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
        placeholder="章节标题"
      />
      <textarea
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        rows={2}
        className="w-full rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-[11.5px] leading-relaxed focus:border-indigo-500/60 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
        placeholder="本章概要"
      />
      <textarea
        value={events}
        onChange={(e) => setEvents(e.target.value)}
        rows={3}
        className="w-full rounded-md border border-neutral-200 bg-white px-2 py-1.5 text-[11.5px] leading-relaxed focus:border-indigo-500/60 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
        placeholder="关键事件，每行一条"
      />
      <div className="flex justify-end gap-1.5">
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10.5px]" onClick={onCancel}>
          <X className="mr-1 h-3 w-3" />
          取消
        </Button>
        <Button
          size="sm"
          className="h-6 bg-indigo-600 px-2 text-[10.5px] text-white hover:bg-indigo-700"
          disabled={saving || !title.trim()}
          onClick={async () => {
            setSaving(true);
            try {
              await onSave({
                title: title.trim(),
                summary: summary.trim() || null,
                key_events: events
                  .split("\n")
                  .map((x) => x.trim())
                  .filter(Boolean),
              });
            } finally {
              setSaving(false);
            }
          }}
        >
          {saving ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Check className="mr-1 h-3 w-3" />
          )}
          保存
        </Button>
      </div>
    </div>
  );
}
