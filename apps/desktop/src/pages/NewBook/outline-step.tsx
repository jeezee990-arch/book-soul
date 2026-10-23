/**
 * 步骤 3 · 大纲与人物。
 *
 * 对应设计稿 s11。大纲流式生成 → 自动抽取人物 → 逐张人物卡生成。
 *
 * 一个改进：旧实现从头到尾只显示 JSON 文本。这里**流式阶段**显示原始片段，
 * **完成之后**（done 事件带回 structure）改用结构化渲染（卷 → 章），
 * 作者一眼能看懂大纲长什么样。
 */

import { Check, Loader2 } from "lucide-react";
import type {
  CharProgress,
  NovelState,
} from "./types";
import type { CompleteOutlineStructure } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  /** 当前阶段 */
  phase: "outline" | "characters" | "done";
  /** 大纲流式原始文本（JSON 片段） */
  outlineText: string;
  /** 大纲完成后的结构（结构化渲染用） */
  outlineStructure: Record<string, unknown> | null;
  novelMeta: NovelState | null;
  charProgress: CharProgress;
  /** 去写第一章 */
  onFinish: () => void;
  /** 再写一本 */
  onRestart: () => void;
}

export default function OutlineStep({
  phase,
  outlineText,
  outlineStructure,
  novelMeta,
  charProgress,
  onFinish,
  onRestart,
}: Props) {
  const savedCount = charProgress.cards.filter((c) => c.id).length;
  const structure = outlineStructure as CompleteOutlineStructure | null;
  const volumes = structure?.volumes ?? [];

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-[19px] font-semibold tracking-tight">
          {phase === "done" ? "作品骨架已就绪" : "正在生成大纲与人物卡"}
        </h2>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-neutral-400">
          {phase === "outline"
            ? "大纲会按「卷 → 章 → 关键事件」结构化输出，随后自动抽取角色。"
            : phase === "characters"
              ? "大纲已完成，正在从大纲抽取角色并生成人物卡。"
              : "大纲与人物卡都已入库，可以直接开始写第一章。"}
        </p>
      </div>

      {/* ===== 大纲 ===== */}
      <section className="mb-6 overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center gap-2 border-b border-neutral-200/70 px-3.5 py-2.5 dark:border-neutral-800/70">
          <h3 className="text-[12.5px] font-semibold">
            {novelMeta ? `《${novelMeta.name}》大纲` : "大纲"}
          </h3>
          {phase === "outline" ? (
            <span className="ml-auto inline-flex items-center gap-1.5 rounded bg-violet-500/15 px-1.5 py-0.5 text-[10.5px] text-violet-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              流式生成中
            </span>
          ) : (
            <span className="ml-auto inline-flex items-center gap-1 rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10.5px] text-emerald-500">
              <Check className="h-3 w-3" />
              已完成
            </span>
          )}
        </div>

        <div className="p-3.5">
          {phase === "outline" ? (
            <pre className="max-h-[280px] overflow-hidden font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-neutral-500 dark:text-neutral-400">
              {outlineText || "…"}
              <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
            </pre>
          ) : (
            <div className="space-y-3">
              {structure?.overall_theme ? (
                <p className="rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-[12px] text-violet-600 dark:text-violet-300">
                  <b className="font-semibold">全篇主题</b>：{structure.overall_theme}
                </p>
              ) : null}

              {volumes.length === 0 ? (
                <p className="text-[12px] text-neutral-400">
                  大纲已生成（自由型）
                </p>
              ) : (
                volumes.map((v) => (
                  <div
                    key={v.name}
                    className="overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800"
                  >
                    <div className="flex items-center gap-2 bg-neutral-100 px-3 py-2 dark:bg-neutral-800/60">
                      <span className="text-[12px] font-semibold">{v.name}</span>
                      <span className="ml-auto text-[10.5px] text-neutral-400">
                        {v.chapters?.length ?? 0} 章
                      </span>
                    </div>
                    {(v.chapters ?? []).map((c, i) => (
                      <div
                        key={`${v.name}-${i}`}
                        className="border-t border-neutral-200 px-3 py-2 dark:border-neutral-800"
                      >
                        <div className="flex items-start gap-2">
                          <span className="mt-px font-mono text-[10.5px] text-violet-400">
                            CH{String(i + 1).padStart(2, "0")}
                          </span>
                          <span className="min-w-0 flex-1 text-[12px] font-medium">
                            {c.title}
                          </span>
                        </div>
                        {c.summary ? (
                          <p className="mt-1 pl-[46px] text-[11.5px] leading-relaxed text-neutral-500 dark:text-neutral-400">
                            {c.summary}
                          </p>
                        ) : null}
                        {c.key_events && c.key_events.length > 0 ? (
                          <ul className="mt-1 space-y-0.5 pl-[46px]">
                            {c.key_events.map((e, ei) => (
                              <li
                                key={ei}
                                className="text-[11px] leading-relaxed text-neutral-400"
                              >
                                · {e}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </section>

      {/* ===== 人物卡 ===== */}
      {phase !== "outline" ? (
        <section className="mb-6">
          <div className="mb-2.5 flex items-center gap-2">
            <h3 className="flex items-baseline gap-2 text-[12.5px] font-semibold">
              人物卡
              <span className="text-[11.5px] font-normal text-neutral-400">
                从大纲自动抽取 · {charProgress.extracted.length} 个角色
              </span>
            </h3>
            {phase === "characters" ? (
              <span className="ml-auto rounded bg-violet-500/15 px-1.5 py-0.5 text-[10.5px] text-violet-400">
                生成 {savedCount} / {charProgress.extracted.length}
              </span>
            ) : null}
          </div>

          {charProgress.cards.length === 0 ? (
            <p className="rounded-lg border border-dashed border-neutral-200 px-3 py-3 text-[11.5px] text-neutral-400 dark:border-neutral-800">
              正在从大纲抽取角色…
            </p>
          ) : (
            <div className="flex flex-wrap gap-2.5">
              {charProgress.cards.map((c) => (
                <div
                  key={c.name}
                  className={cn(
                    "w-[104px] rounded-xl border p-2.5 text-center",
                    c.id !== undefined
                      ? "border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
                      : "border-dashed border-neutral-300 dark:border-neutral-700",
                  )}
                >
                  <div
                    className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-xl text-[16px] font-semibold text-white"
                    style={{
                      background: `linear-gradient(150deg,#${(c.name.charCodeAt(0) * 137) % 4096}, #${(c.name.charCodeAt(0) * 331) % 4096})`,
                    }}
                  >
                    {c.name.slice(0, 1)}
                  </div>
                  <div className="truncate text-[11.5px] font-semibold">
                    {c.name}
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-neutral-400">
                    {c.role}
                  </div>
                  <div className="mt-2 h-0.5 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-700">
                    <i
                      className={cn(
                        "block h-full rounded-full",
                        c.id !== undefined ? "bg-emerald-500" : "bg-violet-500",
                      )}
                      style={{ width: c.id !== undefined ? "100%" : "60%" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {charProgress.error ? (
            <p className="mt-2 text-[11.5px] text-rose-500">{charProgress.error}</p>
          ) : null}
        </section>
      ) : null}

      {/* ===== 完成卡 ===== */}
      {phase === "done" ? (
        <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/10 to-transparent p-4">
          <h4 className="flex items-center gap-2 text-[15px] font-semibold">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-500/15">
              <Check className="h-3.5 w-3.5 text-emerald-500" />
            </span>
            《{novelMeta?.name}》已就绪
          </h4>
          <p className="mt-1.5 text-[12.5px] text-neutral-500 dark:text-neutral-400">
            {volumes.length > 0
              ? `${volumes.length} 卷 · ${volumes.reduce((n, v) => n + (v.chapters?.length ?? 0), 0)} 章`
              : "1 份大纲"}{" "}
            · {savedCount} 个人物卡
          </p>
          <div className="mt-4 flex gap-2.5">
            <button
              type="button"
              onClick={onFinish}
              className="inline-flex h-8 items-center rounded-lg bg-indigo-600 px-4 text-[12.5px] font-medium text-white transition-colors hover:bg-indigo-700"
            >
              去写第一章 →
            </button>
            <button
              type="button"
              onClick={onRestart}
              className="inline-flex h-8 items-center rounded-lg border border-neutral-200 px-4 text-[12.5px] text-neutral-600 transition-colors hover:bg-neutral-100 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              再写一本
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
