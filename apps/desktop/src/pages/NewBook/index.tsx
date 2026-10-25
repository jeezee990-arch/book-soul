/**
 * 开新书（三步向导）。
 *
 * 2026-10 UI 重设计：旧「灵感园」是 idle → seed → plot → outline → character
 * → done 六个状态平铺在一个页面里，操作混乱。
 * 现在收敛为**三步**：种子 → 剧情 → 大纲与人物，顶部有进度条。
 *
 * 另一个关键改进：完成后**自动创建第一章**并跳到写作页 ——
 * 消除"到了创作页还要再点新建章节"的二次断点。
 *
 * 流式契约（AGENTS.md §4.1）：所有生成走 NDJSON 流，逐行读。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import { outlinesApi } from "@/api/outlines";
import { charactersApi } from "@/api/characters";
import { chaptersApi } from "@/api/chapters";
import { readNdjsonStream, detectStreamFailure, parseOutlineStreamEvent, type StreamRequest } from "@/api/streams";
import type { GenreDef } from "@/config/genres";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import SeedStep from "./seed-step";
import PlotStep from "./plot-step";
import OutlineStep from "./outline-step";
import OutlineModePicker, { type OutlineMode } from "./outline-mode-picker";
import type { CharProgress, GenStats, NovelState, PlotVersion } from "./types";
import { EMPTY_CHAR_PROGRESS } from "./types";
import { cn } from "@/lib/utils";

/** 向导状态（3 步）。 */
type WizardStep = "seed" | "plot" | "outline" | "done";

const STEPS: { key: WizardStep; label: string }[] = [
  { key: "seed", label: "种子" },
  { key: "plot", label: "剧情" },
  { key: "outline", label: "大纲与人物" },
];

export default function NewBook() {
  const navigate = useNavigate();
  const refreshNovels = useNovelsStore((s) => s.refresh);
  const setTarget = useWorkspaceStore((s) => s.setTarget);

  const [step, setStep] = useState<WizardStep>("seed");

  // 种子（内存，不持久化）
  const [genre, setGenre] = useState<GenreDef | null>(null);
  const [keywords, setKeywords] = useState<Set<string>>(new Set());

  // 剧情
  const [plotVersions, setPlotVersions] = useState<PlotVersion[]>([]);
  const [plotStreaming, setPlotStreaming] = useState<Record<number, string>>({});
  /** index → 模型思考中的文本（<think> 块；用来显示"模型思考中…"） */
  const [plotThinking, setPlotThinking] = useState<Record<number, string>>({});
  const [plotBusy, setPlotBusy] = useState(false);
  const [chosenPlotIdx, setChosenPlotIdx] = useState<number | null>(null);
  const plotAbortRef = useRef<AbortController | null>(null);
  /** 本次生成已耗时（秒）—— 让用户看到"还在动" */
  const [elapsedSec, setElapsedSec] = useState(0);
  const elapsedRef = useRef<number | null>(null);
  /**
   * 当前耗时的**实时值**（ref）。
   *
   * ⚠️ 不能直接读 state 里的 elapsedSec —— setState 是异步的，
   *    事件回调里读到的还是旧值（AGENTS.md §4.9 同一个坑）。
   */
  const elapsedValueRef = useRef(0);
  /** 剧情阶段的最终统计（模型 + 耗时 + 首字延迟） */
  const [plotStats, setPlotStats] = useState<GenStats | null>(null);

  // 大纲 + 人物
  /** 流式过程中已解析出的**部分**大纲结构（不是原始 JSON 文本） */
  const [outlinePartial, setOutlinePartial] = useState<Record<string, unknown> | null>(null);
  /** 流式过程中已完成的章节数 */
  const [outlineChaptersDone, setOutlineChaptersDone] = useState(0);
  /** 模型思考中的文本（<think> 块）—— 显示"模型思考中…"避免看起来像卡死 */
  const [outlineThinking, setOutlineThinking] = useState("");
  const [outlineMeta, setOutlineMeta] = useState<NovelState | null>(null);
  const [charProgress, setCharProgress] = useState<CharProgress>(EMPTY_CHAR_PROGRESS);
  /** 人物卡生成阶段的思考提示 */
  const [charThinking, setCharThinking] = useState("");
  const [outlinePhase, setOutlinePhase] = useState<
    "outline" | "characters" | "done"
  >("outline");
  const outlineAbortRef = useRef<AbortController | null>(null);
  const charAbortRef = useRef<AbortController | null>(null);
  /** 大纲模式（完整 / 半开放式） */
  const [outlineMode, setOutlineMode] = useState<OutlineMode>("complete");
  /** 大纲阶段的最终统计 */
  const [outlineStats, setOutlineStats] = useState<GenStats | null>(null);
  /** 人物卡阶段的最终统计 */
  const [charStats, setCharStats] = useState<GenStats | null>(null);

  // 作者想法（贯穿所有步骤）
  const [userExtra, setUserExtra] = useState("");
  const [idea, setIdea] = useState("");

  // ===== 步骤 1 → 2：生成剧情 =====

  /** 开始/停止计时器（让用户看到"还在生成"，而不是干等）。 */
  const startElapsed = useCallback(() => {
    elapsedValueRef.current = 0;
    setElapsedSec(0);
    if (elapsedRef.current !== null) window.clearInterval(elapsedRef.current);
    elapsedRef.current = window.setInterval(() => {
      elapsedValueRef.current += 1;
      setElapsedSec(elapsedValueRef.current);
    }, 1000);
  }, []);

  const stopElapsed = useCallback(() => {
    if (elapsedRef.current !== null) {
      window.clearInterval(elapsedRef.current);
      elapsedRef.current = null;
    }
  }, []);

  const startPlotStream = useCallback(async () => {
    if (!genre || keywords.size === 0) return;
    setPlotVersions([]);
    setPlotStreaming({});
    setPlotThinking({});
    setChosenPlotIdx(null);
    setPlotBusy(true);
    setPlotStats(null);
    setStep("plot");
    startElapsed();

    const ctrl = new AbortController();
    plotAbortRef.current = ctrl;
    const req: StreamRequest = inspirationsApi.generatePlotStream(
      {
        genre: genre.name,
        keywords: Array.from(keywords),
        n_versions: 3,
        user_extra: userExtra,
      },
      ctrl.signal,
    );
    try {
      for await (const ev of readNdjsonStream(req.url, {
        method: req.method,
        body: req.body,
        signal: req.signal,
      })) {
        const obj = ev as unknown as Record<string, unknown>;
        const failure = detectStreamFailure(ev);
        if (failure) {
          toast.error("剧情生成失败", { description: failure.message });
          setPlotBusy(false);
          stopElapsed();
          return;
        }
        const event = obj.event as string | undefined;
        const text = obj.text as string | undefined;
        const index = obj.index as number | undefined;
        if (event === "version_start") {
          setPlotStreaming((s) => ({ ...s, [index!]: "" }));
        } else if (event === "thinking") {
          // 推理模型的思考阶段：不能静默丢掉（否则前端一个字都收不到，
          // 用户看到的就是"卡住不动"）。存下来显示"模型思考中…"。
          setPlotThinking((s) => ({
            ...s,
            [index!]: (s[index!] ?? "") + (text ?? ""),
          }));
        } else if (event === "delta" && text) {
          setPlotStreaming((s) => ({
            ...s,
            [index!]: (s[index!] ?? "") + text,
          }));
        } else if (event === "version_done") {
          setPlotVersions((v) => {
            const without = v.filter((x) => x.index !== index);
            return [
              ...without,
              { index: index!, summary: obj.summary as string },
            ].sort((a, b) => a.index - b.index);
          });
        } else if (event === "done") {
          // 记录"这次用的是哪个模型、耗时多少秒"（用户明确要求）
          const backendElapsed = obj.elapsed_sec as number | undefined;
          const backendFirst = obj.first_delta_sec as number | null | undefined;
          setPlotStats({
            model: (obj.model as string) || "",
            elapsedSec: backendElapsed ?? elapsedValueRef.current,
            firstDeltaSec: backendFirst ?? null,
          });
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!msg.includes("abort")) {
        toast.error("剧情生成中断", { description: msg });
      }
    } finally {
      setPlotBusy(false);
      stopElapsed();
    }
  }, [genre, keywords, userExtra, startElapsed, stopElapsed]);

  // ===== 步骤 2 → 3：选剧情 → 生成大纲 =====

  /**
   * 生成大纲（剧情 → 大纲）。
   *
   * ⚠️ `targetIdx` 用来**显式指定**用哪个剧情版本。
   *    不传时回退到 state 里的 `chosenPlotIdx` —— 但 state 是异步的，
   *    同一帧里读到的还是旧值：「点了卡片就自动生成」的做法会拿上一张卡的
   *    剧情去生成大纲（第一次点读到 null 直接 return，第二次点才生效）。
   *    所以卡片只负责"选中"，真正生成走按钮，传入显式索引。
   */
  const startOutlineStream = useCallback(async (targetIdx?: number | null) => {
    const idx = targetIdx ?? chosenPlotIdx;
    if (idx === null || idx === undefined) return;
    const plot = plotVersions.find((v) => v.index === idx);
    if (!plot) return;

    setOutlinePartial(null);
    setOutlineChaptersDone(0);
    setOutlineThinking("");
    setOutlineMeta(null);
    setOutlineStats(null);
    setCharProgress(EMPTY_CHAR_PROGRESS);
    setCharThinking("");
    setCharStats(null);
    setOutlinePhase("outline");
    setStep("outline");
    startElapsed();

    const ctrl = new AbortController();
    outlineAbortRef.current = ctrl;
    const req: StreamRequest = outlinesApi.generateStream(
      {
        genre: genre?.name ?? "通用",
        plot_summary: plot.summary,
        keywords: Array.from(keywords),
        novel_name: undefined,
        outline_type: outlineMode,
        user_extra: userExtra,
      },
      ctrl.signal,
    );
    try {
      for await (const ev of readNdjsonStream(req.url, {
        method: req.method,
        body: req.body,
        signal: req.signal,
      })) {
        const parsed = parseOutlineStreamEvent(ev);
        if (parsed.kind === "error") {
          // 失败就退回剧情页 —— 否则界面停在"流式生成中…"永远转圈
          toast.error("大纲生成失败", { description: parsed.message });
          setOutlinePartial(null);
          setOutlineThinking("");
          setStep("plot");
          return;
        }
        if (parsed.kind === "thinking") {
          // 推理模型思考阶段：显示"模型思考中…"，而不是让用户对着空白等待
          setOutlineThinking((s) => s + parsed.text);
        } else if (parsed.kind === "partial") {
          // 后端推的是**已解析好的结构**（不是原始 JSON 文本）——
          // 前端只管渲染中文剧情，不用解析半截 JSON。
          setOutlinePartial(parsed.structure);
          setOutlineChaptersDone(parsed.chaptersDone);
        } else if (parsed.kind === "done") {
          setOutlineMeta({
            id: parsed.novelId,
            name: parsed.novelName,
            outlineStructure: parsed.structure,
          });
          setOutlineStats({
            model: parsed.model,
            elapsedSec: parsed.elapsedSec ?? elapsedValueRef.current,
            firstDeltaSec: parsed.firstDeltaSec,
          });
          setOutlinePhase("characters");
          // 自动触发人物卡生成
          void startCharacterStream(parsed.novelId, parsed.structure);
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!msg.includes("abort")) {
        toast.error("大纲生成中断", { description: msg });
      }
      setStep("plot");
    }
  }, [chosenPlotIdx, plotVersions, genre, keywords, userExtra, outlineMode, startElapsed]);

  // ===== 步骤 3：从大纲生成人物卡 =====

  const startCharacterStream = useCallback(
    async (novelId: number, outline: Record<string, unknown>) => {
      setCharProgress(EMPTY_CHAR_PROGRESS);
      setCharThinking("");
      setCharStats(null);
      setOutlinePhase("outline");
      // 人物卡是独立的一次生成 —— 重新计时
      startElapsed();
      const ctrl = new AbortController();
      charAbortRef.current = ctrl;
      const req: StreamRequest = charactersApi.generateFromOutlineStream(
        novelId,
        { outline, genre: genre?.name ?? "通用", user_extra: userExtra },
        ctrl.signal,
      );
      try {
        for await (const ev of readNdjsonStream(req.url, {
          method: req.method,
          body: req.body,
          signal: req.signal,
        })) {
          const obj = ev as unknown as Record<string, unknown>;
          const failure = detectStreamFailure(ev);
          if (failure) {
            setCharProgress((s) => ({ ...s, error: failure.message }));
            toast.error("人物卡生成失败", { description: failure.message });
            return;
          }
          const event = obj.event as string | undefined;
          if (event === "thinking") {
            // 推理模型思考阶段：给个提示，别让用户以为卡死了
            setCharThinking((s) => s + ((obj.text as string) ?? ""));
          } else if (event === "extract_done") {
            setCharProgress((s) => ({
              ...s,
              extracted: (obj.characters as { name: string; role: string }[]) ?? [],
            }));
          } else if (event === "card_start") {
            setCharProgress((s) => ({
              ...s,
              cards: [
                ...s.cards,
                { name: obj.name as string, role: obj.role as string, text: "" },
              ],
            }));
          } else if (event === "card_delta") {
            const name = obj.name as string;
            const text = obj.text as string;
            setCharProgress((s) => ({
              ...s,
              cards: s.cards.map((c) =>
                c.name === name && !c.id ? { ...c, text: c.text + text } : c,
              ),
            }));
          } else if (event === "card_done") {
            const name = obj.name as string;
            const id = obj.id as number;
            setCharProgress((s) => ({
              ...s,
              cards: s.cards.map((c) => (c.name === name ? { ...c, id } : c)),
            }));
          } else if (event === "done") {
            setCharStats({
              model: (obj.model as string) || "",
              elapsedSec: (obj.elapsed_sec as number | undefined) ?? elapsedValueRef.current,
              firstDeltaSec: null,
            });
            setOutlinePhase("done");
            setStep("done");
            toast.success(`已生成 ${(obj.saved_count as number) ?? 0} 个人物卡`);
          }
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!msg.includes("abort")) {
          toast.error("人物卡生成中断", { description: msg });
        }
      }
    },
    [genre, userExtra, startElapsed],
  );

  // 大纲阶段 → 退回剧情页重选（不然选错一条只能整本重开）
  const handleBackToPlot = useCallback(() => {
    outlineAbortRef.current?.abort();
    charAbortRef.current?.abort();
    setOutlinePartial(null);
    setOutlineChaptersDone(0);
    setOutlineThinking("");
    setOutlineMeta(null);
    setOutlineStats(null);
    setCharProgress(EMPTY_CHAR_PROGRESS);
    setCharThinking("");
    setCharStats(null);
    setOutlinePhase("outline");
    setStep("plot");
  }, []);

  // ===== 完成 → 自动建第一章 → 跳写作页 =====

  const handleFinish = useCallback(async () => {
    if (!outlineMeta) return;
    const novelId = outlineMeta.id;

    // 从大纲第一章建正文章节
    try {
      const existing = await chaptersApi.list(novelId);
      if (existing.length === 0) {
        const first = firstChapterOf(outlineMeta.outlineStructure);
        if (first) {
          const ch = await chaptersApi.create({
            novel_id: novelId,
            chapter_number: 1,
            title: first.title,
            outline: first.outline,
            status: "outline",
          });
          setTarget(novelId, ch.id, `第 1 章 · ${first.title}`);
        } else {
          setTarget(novelId, null);
        }
      } else {
        setTarget(novelId, existing[0].id);
      }
    } catch {
      setTarget(novelId, null);
    }

    await refreshNovels();
    navigate("/");
  }, [outlineMeta, setTarget, refreshNovels, navigate]);

  // 离开页面 → 取消未完成请求
  useEffect(() => {
    return () => {
      plotAbortRef.current?.abort();
      outlineAbortRef.current?.abort();
      charAbortRef.current?.abort();
      if (elapsedRef.current !== null) {
        window.clearInterval(elapsedRef.current);
        elapsedRef.current = null;
      }
    };
  }, []);

  // ===== 底部想法输入 =====

  const handleIdeaSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      setUserExtra((prev) => (prev ? prev + "\n" + trimmed : trimmed));
      // 种子步骤额外把文本当关键词
      if (step === "seed") {
        setKeywords((prev) => {
          if (prev.has(trimmed)) return prev;
          const next = new Set(prev);
          next.add(trimmed);
          return next;
        });
        toast.success(`已加入关键词：${trimmed.slice(0, 24)}`);
      } else {
        toast.info("想法已记录，会随下一次生成发送", {
          description: trimmed.slice(0, 40),
        });
      }
      setIdea("");
    },
    [step],
  );

  const ideaPlaceholder = useMemo(() => {
    switch (step) {
      case "seed":
        return "描述你想要的剧情氛围 / 主角特点 / 题材混搭…（回车即加入关键词）";
      case "plot":
        return "对剧情的补充想法…";
      case "outline":
        return "对大纲或人物的特别要求…";
      default:
        return "（已完成，可以去写作页继续）";
    }
  }, [step]);

  const stepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 步骤条 */}
      <div className="flex h-[58px] shrink-0 items-center justify-center border-b border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        {STEPS.map((s, i) => {
          const done = stepIndex > i || step === "done";
          const on = step === s.key;
          return (
            <div key={s.key} className="flex items-center">
              {i > 0 ? (
                <span
                  className={cn(
                    "mx-2 h-px w-14",
                    done || stepIndex > i - 1
                      ? "bg-indigo-500/50"
                      : "bg-neutral-200 dark:bg-neutral-800",
                  )}
                />
              ) : null}
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "grid h-[23px] w-[23px] place-items-center rounded-full font-mono text-[11px] transition-colors",
                    on
                      ? "bg-indigo-500 text-white"
                      : done
                        ? "bg-emerald-500 text-neutral-900"
                        : "border border-neutral-200 text-neutral-400 dark:border-neutral-800",
                  )}
                >
                  {done && !on ? "✓" : i + 1}
                </span>
                <span
                  className={cn(
                    "text-[12.5px]",
                    on
                      ? "font-semibold"
                      : done
                        ? "text-neutral-500 dark:text-neutral-400"
                        : "text-neutral-400",
                  )}
                >
                  {s.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* 内容 */}
      <div className="min-h-0 flex-1 overflow-y-auto pb-28">
        <div className="mx-auto w-[840px] max-w-[94%] py-8">
          {step === "seed" ? (
            <>
              <h2 className="text-[19px] font-semibold tracking-tight">
                从一个种子开始
              </h2>
              <p className="mt-1.5 mb-6 text-[12.5px] leading-relaxed text-neutral-400">
                选题材和关键词，AI 会给出 3 个不同的剧情走向供你挑。
                <br />
                随时可以在下面补充你的想法，它会贯穿后面每一步。
              </p>
              <SeedStep
                genre={genre}
                onSelectGenre={setGenre}
                keywords={keywords}
                onToggleKeyword={(kw) =>
                  setKeywords((prev) => {
                    const next = new Set(prev);
                    if (next.has(kw)) next.delete(kw);
                    else next.add(kw);
                    return next;
                  })
                }
                onRemoveKeyword={(kw) =>
                  setKeywords((prev) => {
                    const next = new Set(prev);
                    next.delete(kw);
                    return next;
                  })
                }
                onClearKeywords={() => setKeywords(new Set())}
              />
              <div className="mt-7 flex justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => navigate("/")}
                  className="h-9 rounded-lg px-4 text-[13px] text-neutral-500 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={() => void startPlotStream()}
                  disabled={!genre || keywords.size === 0}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-violet-600 px-5 text-[13px] font-medium text-white transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  生成 3 个剧情
                </button>
              </div>
            </>
          ) : null}

          {step === "plot" ? (
            <>
              <PlotStep
                genre={genre}
                keywords={keywords}
                versions={plotVersions}
                streaming={plotStreaming}
                thinking={plotThinking}
                isStreaming={plotBusy}
                elapsedSec={elapsedSec}
                stats={plotStats}
                chosenIdx={chosenPlotIdx}
                onChoose={(idx) => {
                  // 只负责"选中"。生成走下面的按钮 —— 按钮显式传索引，
                  // 避免"点了卡片就自动生成"时读到上一轮的陈旧 state。
                  setChosenPlotIdx(idx);
                }}
              />
              {chosenPlotIdx !== null && !plotBusy ? (
                /* 选好剧情后，选"要哪种大纲"（2026-10-25 新增） */
                <section className="mt-7 rounded-xl border border-neutral-200 p-4 dark:border-neutral-800">
                  <h3 className="text-[13px] font-semibold">接下来生成哪种大纲？</h3>
                  <p className="mt-1 mb-3 text-[11.5px] leading-relaxed text-neutral-400">
                    两种都可以随时换成另一种 —— 选错了在下一步点「← 换一条剧情」回来重选。
                  </p>
                  <OutlineModePicker
                    value={outlineMode}
                    onChange={setOutlineMode}
                    disabled={plotBusy}
                  />
                  <div className="mt-4 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        plotAbortRef.current?.abort();
                        stopElapsed();
                        setStep("seed");
                      }}
                      className="h-9 rounded-lg px-4 text-[13px] text-neutral-500 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
                    >
                      ← 回到种子
                    </button>
                    <button
                      type="button"
                      onClick={() => void startOutlineStream(chosenPlotIdx)}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-violet-600 px-5 text-[13px] font-medium text-white transition-colors hover:bg-violet-700"
                    >
                      用走向 {String.fromCharCode(64 + chosenPlotIdx)} 生成
                      {outlineMode === "semi_open" ? "半开放大纲" : "完整大纲"}
                    </button>
                  </div>
                </section>
              ) : (
                <div className="mt-7 flex justify-between">
                  <button
                    type="button"
                    onClick={() => {
                      plotAbortRef.current?.abort();
                      stopElapsed();
                      setStep("seed");
                    }}
                    className="h-9 rounded-lg px-4 text-[13px] text-neutral-500 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
                  >
                    ← 回到种子
                  </button>
                </div>
              )}
            </>
          ) : null}

          {step === "outline" || step === "done" ? (
            <OutlineStep
              phase={outlinePhase}
              outlinePartial={outlinePartial}
              outlineChaptersDone={outlineChaptersDone}
              outlineThinking={outlineThinking}
              outlineStructure={outlineMeta?.outlineStructure ?? null}
              novelMeta={outlineMeta}
              charProgress={charProgress}
              charThinking={charThinking}
              outlineStats={outlineStats}
              charStats={charStats}
              elapsedSec={elapsedSec}
              outlineMode={outlineMode}
              onFinish={() => void handleFinish()}
              onBack={handleBackToPlot}
              onRestart={() => {
                setStep("seed");
                setGenre(null);
                setKeywords(new Set());
                setPlotVersions([]);
                setPlotStreaming({});
                setPlotThinking({});
                setChosenPlotIdx(null);
                setOutlinePartial(null);
                setOutlineChaptersDone(0);
                setOutlineThinking("");
                setOutlineMeta(null);
                setOutlineStats(null);
                setCharProgress(EMPTY_CHAR_PROGRESS);
                setCharThinking("");
                setCharStats(null);
                setOutlinePhase("outline");
              }}
            />
          ) : null}
        </div>
      </div>

      {/* 底部想法输入（常驻，状态驱动 placeholder） */}
      <div className="shrink-0 border-t border-neutral-200 bg-white px-6 py-3 dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mx-auto flex max-w-[840px] items-center gap-3 rounded-xl border border-neutral-200 bg-neutral-50 px-3.5 py-2.5 focus-within:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-800/40 dark:focus-within:border-neutral-700">
          <span className="shrink-0 text-[12.5px] text-violet-400">✦</span>
          <input
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleIdeaSubmit(idea);
              }
            }}
            placeholder={ideaPlaceholder}
            disabled={step === "done"}
            className="min-w-0 flex-1 bg-transparent text-[12.5px] outline-none placeholder:text-neutral-400 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => handleIdeaSubmit(idea)}
            disabled={!idea.trim() || step === "done"}
            className="shrink-0 rounded-lg bg-neutral-200 px-3 py-1.5 text-[11.5px] text-neutral-600 transition-colors hover:bg-neutral-300 disabled:opacity-40 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700"
          >
            记下
          </button>
        </div>
      </div>
    </div>
  );
}

/** 从大纲结构里取第一章（标题 + 概要），取不到返回 null。 */
function firstChapterOf(
  structure: Record<string, unknown>,
): { title: string; outline: string | null } | null {
  const volumes = (structure.volumes ?? []) as {
    chapters?: { title: string; summary?: string | null; key_events?: string[] }[];
  }[];
  for (const v of volumes) {
    const c = v.chapters?.[0];
    if (c) {
      const outline = [
        c.summary,
        ...(c.key_events ?? []).map((e) => `· ${e}`),
      ]
        .filter(Boolean)
        .join("\n");
      return { title: c.title, outline: outline || null };
    }
  }
  return null;
}
