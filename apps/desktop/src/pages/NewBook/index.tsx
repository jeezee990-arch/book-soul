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
import { readNdjsonStream, detectStreamFailure, parseOutlineStreamEvent, appendThinking, type StreamRequest } from "@/api/streams";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useNewBookStore, type NewBookStep } from "@/stores/newbook-store";
import SeedStep from "./seed-step";
import PlotStep from "./plot-step";
import OutlineStep from "./outline-step";
import OutlineModePicker from "./outline-mode-picker";
import OutlineScaleBar from "./outline-scale-bar";
import IdeaChips from "./idea-chips";
import { EMPTY_CHAR_PROGRESS } from "./types";
import { parseScaleFromText } from "@/lib/outline-scale";
import { mergeVolumeIntoStructure, fillPendingChapters } from "@/lib/outline-merge";
import { cn } from "@/lib/utils";

const STEPS: { key: NewBookStep; label: string }[] = [
  { key: "seed", label: "种子" },
  { key: "plot", label: "剧情" },
  { key: "outline", label: "大纲与人物" },
];

/**
 * 三条流的 AbortController（**模块级**）。
 *
 * 为什么不用 useRef：组件卸载后 ref 还在但没人能拿到它 → 后台正在跑的
 * 生成就停不掉了。模块级变量任何时候都能访问。
 */
let plotAbort: AbortController | null = null;
let outlineAbort: AbortController | null = null;
let charAbort: AbortController | null = null;

export default function NewBook() {
  const navigate = useNavigate();
  const refreshNovels = useNovelsStore((s) => s.refresh);
  const setTarget = useWorkspaceStore((s) => s.setTarget);

  // ===== 持久化进度（切页面回来还在）=====
  const step = useNewBookStore((s) => s.step);
  const setStep = useNewBookStore((s) => s.setStep);
  const genre = useNewBookStore((s) => s.genre);
  const setGenre = useNewBookStore((s) => s.setGenre);
  const keywords = useNewBookStore((s) => s.keywords);
  const toggleKeyword = useNewBookStore((s) => s.toggleKeyword);
  const removeKeyword = useNewBookStore((s) => s.removeKeyword);
  const clearKeywords = useNewBookStore((s) => s.clearKeywords);
  /** 作者想法词条（每次发送加一条；见 IdeaChips） */
  const ideas = useNewBookStore((s) => s.ideas);
  const addIdea = useNewBookStore((s) => s.addIdea);
  const removeIdea = useNewBookStore((s) => s.removeIdea);
  const plotVersions = useNewBookStore((s) => s.plotVersions);
  const setPlotVersions = useNewBookStore((s) => s.setPlotVersions);
  const chosenPlotIdx = useNewBookStore((s) => s.chosenPlotIdx);
  const setChosenPlotIdx = useNewBookStore((s) => s.setChosenPlotIdx);
  const outlineMode = useNewBookStore((s) => s.outlineMode);
  const setOutlineMode = useNewBookStore((s) => s.setOutlineMode);
  /** 大纲规模（总章数 / 每卷章数 / 每章字数）——硬指标，后端写进 prompt */
  const outlineScale = useNewBookStore((s) => s.outlineScale);
  const setOutlineScale = useNewBookStore((s) => s.setOutlineScale);
  const autoFillOutlineScale = useNewBookStore((s) => s.autoFillOutlineScale);
  const outlineScaleTouched = useNewBookStore((s) => s.outlineScaleTouched);
  const outlineMeta = useNewBookStore((s) => s.outlineMeta);
  const setOutlineMeta = useNewBookStore((s) => s.setOutlineMeta);
  /** 本次向导建出来的书名（重生成时复用同一本作品） */
  const novelName = useNewBookStore((s) => s.novelName);
  const setNovelName = useNewBookStore((s) => s.setNovelName);
  const charProgress = useNewBookStore((s) => s.charProgress);
  const setCharProgress = useNewBookStore((s) => s.setCharProgress);
  const plotStats = useNewBookStore((s) => s.plotStats);
  const setPlotStats = useNewBookStore((s) => s.setPlotStats);
  const outlineStats = useNewBookStore((s) => s.outlineStats);
  const setOutlineStats = useNewBookStore((s) => s.setOutlineStats);
  const charStats = useNewBookStore((s) => s.charStats);
  const setCharStats = useNewBookStore((s) => s.setCharStats);
  const resetAll = useNewBookStore((s) => s.resetAll);

  // ===== 瞬时状态（放 store：组件卸载后 set 依然有效，后台生成能跑完）=====
  const plotStreaming = useNewBookStore((s) => s.plotStreaming);
  const setPlotStreaming = useNewBookStore((s) => s.setPlotStreaming);
  /** index → 模型思考中的文本（<think> 块；用来显示"模型思考中…"） */
  const plotThinking = useNewBookStore((s) => s.plotThinking);
  const setPlotThinking = useNewBookStore((s) => s.setPlotThinking);
  /** index → 该版本的失败原因（单版本失败不影响其它版本） */
  const plotErrors = useNewBookStore((s) => s.plotErrors);
  const setPlotErrors = useNewBookStore((s) => s.setPlotErrors);
  const plotBusy = useNewBookStore((s) => s.plotBusy);
  const setPlotBusy = useNewBookStore((s) => s.setPlotBusy);
  /** 本次生成已耗时（秒）—— 让用户看到"还在动" */
  const elapsedStartedAt = useNewBookStore((s) => s.elapsedStartedAt);
  const setElapsedStartedAt = useNewBookStore((s) => s.setElapsedStartedAt);
  /**
   * 每秒 tick 一次，只为触发重渲染。
   *
   * ⚠️ 显示的秒数是**算出来的**（now - elapsedStartedAt），不是累加的 ——
   *    累加值在"切到别的页面再回来"时会停在切走的那一刻。
   */
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (elapsedStartedAt === null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [elapsedStartedAt]);
  const elapsedSec =
    elapsedStartedAt === null ? 0 : Math.floor((now - elapsedStartedAt) / 1000);
  const elapsedValueRef = useRef(0);

  // 把算出来的秒数同步到 ref —— 后端没给 elapsed_sec 时用它兜底。
  //
  // ⚠️ 2026-10-25 巡检：这个 ref 以前**永远是 0**（声明了但没人更新），
  // 于是「后端没返回耗时」时统计显示 0 秒。现在每次渲染同步一次。
  useEffect(() => {
    elapsedValueRef.current = elapsedSec;
  }, [elapsedSec]);

  // 大纲 + 人物
  /** 流式过程中已解析出的**部分**大纲结构（不是原始 JSON 文本） */
  const outlinePartial = useNewBookStore((s) => s.outlinePartial);
  const setOutlinePartial = useNewBookStore((s) => s.setOutlinePartial);
  /** 流式过程中已完成的章节数 */
  const outlineChaptersDone = useNewBookStore((s) => s.outlineChaptersDone);
  const setOutlineChaptersDone = useNewBookStore((s) => s.setOutlineChaptersDone);
  /** 各卷细化状态（阶段二并行补细节时显示"哪一卷好了"） */
  const outlineVolumeStatus = useNewBookStore((s) => s.outlineVolumeStatus);
  const setOutlineVolumeStatus = useNewBookStore((s) => s.setOutlineVolumeStatus);
  /** 模型思考中的文本（<think> 块）—— 显示"模型思考中…"避免看起来像卡死 */
  const outlineThinking = useNewBookStore((s) => s.outlineThinking);
  const setOutlineThinking = useNewBookStore((s) => s.setOutlineThinking);
  /** 人物卡生成阶段的思考提示 */
  const charThinking = useNewBookStore((s) => s.charThinking);
  const setCharThinking = useNewBookStore((s) => s.setCharThinking);
  const outlinePhase = useNewBookStore((s) => s.outlinePhase);
  const setOutlinePhase = useNewBookStore((s) => s.setOutlinePhase);
  /** 大纲是否正在生成（区分"生成中"与"上次被刷新打断"） */
  const outlineBusy = useNewBookStore((s) => s.outlineBusy);
  const setOutlineBusy = useNewBookStore((s) => s.setOutlineBusy);

  /** 底部输入框的临时文本 */
  const [idea, setIdea] = useState("");

  /** 发给后端的"作者个人想法"——把词条拼成多行文本 */
  const userExtra = useMemo(() => ideas.join("\n"), [ideas]);

  /** 选中的那条剧情摘要（用于检测大纲是否沿着剧情走） */
  const chosenPlotSummary = useMemo(() => {
    if (chosenPlotIdx === null) return "";
    return plotVersions.find((v) => v.index === chosenPlotIdx)?.summary ?? "";
  }, [chosenPlotIdx, plotVersions]);

  // ===== 规模自动识别 =====
  //
  // 作者在想法里写"共100章""每章3000字" → 自动填进规模设置。
  // ⚠️ 作者**手动改过**之后就不再自动覆盖（手填的值更权威）。
  const detectedScale = useMemo(() => parseScaleFromText(userExtra), [userExtra]);

  useEffect(() => {
    if (detectedScale) autoFillOutlineScale(detectedScale);
  }, [detectedScale, autoFillOutlineScale]);

  // ===== 步骤 1 → 2：生成剧情 =====

  /**
   * 开始/停止计时。
   *
   * 计时器本身在组件里（每秒 tick 触发重渲染），但**起始时刻存在 store** ——
   * 这样切到别的页面再回来，秒数能接着算，而不是停在切走那一刻。
   */
  const startElapsed = useCallback(() => {
    elapsedValueRef.current = 0;
    setElapsedStartedAt(Date.now());
  }, [setElapsedStartedAt]);

  const stopElapsed = useCallback(() => {
    setElapsedStartedAt(null);
  }, [setElapsedStartedAt]);

  /** 停止剧情生成（用户主动中断） */
  const stopPlotStream = useCallback(() => {
    plotAbort?.abort();
    setPlotBusy(false);
    stopElapsed();
  }, [stopElapsed]);

  const startPlotStream = useCallback(async () => {
    if (!genre || keywords.length === 0) return;
    setPlotVersions([]);
    setPlotStreaming({});
    setPlotThinking({});
    setPlotErrors({});
    setChosenPlotIdx(null);
    setPlotBusy(true);
    setPlotStats(null);
    setStep("plot");
    startElapsed();

    const ctrl = new AbortController();
    plotAbort = ctrl;
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
          // ⚠️ 后端现在给**单个版本**的错误带上 index（2026-10-25）。
          //    一个版本失败不应该让另外两个也白跑 —— 只标记那张卡，
          //    继续等剩下的版本。整体失败（没有 index）才中断。
          const errIdx = typeof obj.index === "number" ? obj.index : null;
          if (errIdx !== null) {
            setPlotErrors((s) => ({ ...s, [errIdx]: failure.message }));
            continue;
          }
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
          // ⚠️ 后端已把思考里的英文/代码净身掉（2026-10-29 用户实测图1）：
          //    净身后为空时用中文占位符顶上，否则提示消失、界面像卡死。
          setPlotThinking((s) => {
            const next = appendThinking(s[index!] ?? "", text ?? "");
            return { ...s, [index!]: next };
          });
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
    if (!plot) {
      // ⚠️ 2026-10-25 巡检：剧情生成中途"停止"时卡片还有半截文本、
      //    仍可点选，但**没有 version_done** → 这里拿不到完整剧情。
      //    原来直接 return → 点了按钮什么都不发生（用户以为界面坏了）。
      toast.error("这条剧情还没生成完", {
        description: "点「停止」后留下的半截内容无法用来生成大纲，请重新生成剧情",
      });
      return;
    }

    setOutlinePartial(null);
    setOutlineChaptersDone(0);
    setOutlineVolumeStatus({});
    setOutlineThinking("");
    setOutlineMeta(null);
    setOutlineStats(null);
    setCharProgress(EMPTY_CHAR_PROGRESS);
    setCharThinking("");
    setCharStats(null);
    setOutlinePhase("outline");
    setOutlineBusy(true);
    setStep("outline");
    startElapsed();

    const ctrl = new AbortController();
    outlineAbort = ctrl;
    const req: StreamRequest = outlinesApi.generateStream(
      {
        genre: genre?.name ?? "通用",
        plot_summary: plot.summary,
        keywords: Array.from(keywords),
        // 书名：同一向导内复用（后端按名 upsert → 覆盖同一本而不是新建）
        novel_name: novelName ?? undefined,
        outline_type: outlineMode,
        user_extra: userExtra,
        // 规模是**硬指标**：写进 prompt 要求模型照做
        total_chapters: outlineScale.totalChapters,
        chapters_per_volume: outlineScale.chaptersPerVolume,
        words_per_chapter: outlineScale.wordsPerChapter,
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
          setOutlineBusy(false);
          setStep("plot");
          return;
        }
        if (parsed.kind === "thinking") {
          // 推理模型思考阶段：显示"模型思考中…"，而不是让用户对着空白等待
          // ⚠️ 净身后为空时用中文占位符顶上（见 plot 分支的注释）
          setOutlineThinking((s) => appendThinking(s, parsed.text));
        } else if (parsed.kind === "partial") {
          // 后端推的是**已解析好的结构**（不是原始 JSON 文本）——
          // 前端只管渲染中文剧情，不用解析半截 JSON。
          setOutlinePartial(parsed.structure);
          setOutlineChaptersDone(parsed.chaptersDone);
        } else if (parsed.kind === "skeleton") {
          // 阶段一完成：全书卷章结构齐了
          setOutlinePartial(parsed.structure);
          setOutlineChaptersDone(parsed.chaptersDone);
        } else if (parsed.kind === "volume_start") {
          setOutlineVolumeStatus((s) => ({ ...s, [parsed.index]: "running" }));
        } else if (parsed.kind === "volume_done") {
          // 某一卷的细节补齐 → 按下标替换那一卷
          setOutlinePartial((prev) =>
            mergeVolumeIntoStructure(prev, parsed.index, parsed.volume),
          );
          setOutlineVolumeStatus((s) => ({ ...s, [parsed.index]: "done" }));
        } else if (parsed.kind === "volume_error") {
          // 单卷失败不影响其它卷
          setOutlineVolumeStatus((s) => ({ ...s, [parsed.index]: "error" }));
          // ⚠️ 需求7：失败的卷也要补占位概要 —— 否则用户看到的是
          //    "一堆只有标题的空章节"（与后端 merge_volume_details 保持一致）
          setOutlinePartial((prev) => fillPendingChapters(prev, parsed.index));
        } else if (parsed.kind === "done") {
          setOutlineBusy(false);
          setOutlineMeta({
            id: parsed.novelId,
            name: parsed.novelName,
            outlineStructure: parsed.structure,
          });
          // 记住书名：退回剧情页再生成时复用同一本书（而不是新建一本）
          setNovelName(parsed.novelName);
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
      setOutlineBusy(false);
      setStep("plot");
    }
  }, [
    chosenPlotIdx,
    plotVersions,
    genre,
    keywords,
    userExtra,
    outlineMode,
    outlineScale,
    startElapsed,
  ]);

  // ===== 步骤 3：从大纲生成人物卡 =====

  const startCharacterStream = useCallback(
    async (novelId: number, outline: Record<string, unknown>) => {
      setCharProgress(EMPTY_CHAR_PROGRESS);
      setCharThinking("");
      setCharStats(null);
      // ⚠️ 2026-10-25 巡检：这里原来写的是 setOutlinePhase("outline")，
      //    把调用方刚设的 "characters" 覆盖回去 → React 批处理后最终是
      //    "outline" → 人物卡整块被 phase !== "outline" 挡住不渲染，
      //    用户几分钟都看不到人物卡进度。现在必须停在 "characters"。
      setOutlinePhase("characters");
      // 人物卡是独立的一次生成 —— 重新计时
      startElapsed();
      const ctrl = new AbortController();
      charAbort = ctrl;
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
            // ⚠️ 净身后为空时用中文占位符顶上
            setCharThinking((s) => appendThinking(s, (obj.text as string) ?? ""));
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
    outlineAbort?.abort();
    charAbort?.abort();
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

  // 离开页面 → **不中断**正在跑的生成
  //
  // ⚠️ 2026-10-25 改：以前这里 abort 掉所有请求，用户切个页面回来
  //    生成就白跑了。现在生成结果写进 store（组件卸载后 set 依然有效），
  //    所以让请求**继续在后台跑完**，回来直接看到结果。
  //    停止生成请用「停止」按钮（见 plot-step / outline-step）。
  useEffect(() => {
    // 组件卸载时不 abort：让后台把生成跑完（结果写进 store，回来可见）
  }, []);

  // ===== 底部想法输入 =====

  const handleIdeaSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      // 种子步骤：输入的文本当**关键词**（进 prompt 的关键词位）
      if (step === "seed") {
        if (!keywords.includes(trimmed)) toggleKeyword(trimmed);
        toast.success(`已加入关键词：${trimmed.slice(0, 24)}`);
      } else {
        // 其它步骤：变成一条**想法词条**（可见、可删、会随生成发送）
        addIdea(trimmed);
      }
      setIdea("");
    },
    [step, keywords, toggleKeyword, addIdea],
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
  const keywordCount = keywords.length;

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
                onToggleKeyword={toggleKeyword}
                onRemoveKeyword={removeKeyword}
                onClearKeywords={clearKeywords}
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
                  disabled={!genre || keywordCount === 0}
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
                errors={plotErrors}
                isStreaming={plotBusy}
                elapsedSec={elapsedSec}
                stats={plotStats}
                onStop={stopPlotStream}
                chosenIdx={chosenPlotIdx}
                onChoose={(idx) => {
                  // 只负责"选中"。生成走下面的按钮 —— 按钮显式传索引，
                  // 避免"点了卡片就自动生成"时读到上一轮的陈旧 state。
                  setChosenPlotIdx(idx);
                }}
              />
              {/* 想法词条：每次发送想法加一条，鼠标移上去才露出删除按钮 */}
              <IdeaChips ideas={ideas} onRemove={removeIdea} disabled={plotBusy} />
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
                  {/* 规模设置：作者明确写死的章数/字数（以前被 prompt 里的
                      "20-40 章"无视 —— 现在是硬指标） */}
                  <div className="mt-3">
                    <OutlineScaleBar
                      value={outlineScale}
                      onChange={setOutlineScale}
                      canRedetect={Boolean(detectedScale) && !outlineScaleTouched}
                      disabled={plotBusy}
                    />
                  </div>
                  <div className="mt-4 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        plotAbort?.abort();
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
                      plotAbort?.abort();
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
              outlineVolumeStatus={outlineVolumeStatus}
              plotSummary={chosenPlotSummary}
              generating={outlineBusy}
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
              onBack={handleBackToPlot}              onRestart={() => {
                // 「再写一本」：清空持久化进度 + 本地瞬时状态
                resetAll();
                setPlotStreaming({});
                setPlotThinking({});
                setPlotErrors({});
                setOutlinePartial(null);
                setOutlineChaptersDone(0);
                setOutlineThinking("");
                setCharThinking("");
                setOutlinePhase("outline");
              }}
            />
          ) : null}

          {/* 想法词条：大纲步骤也能看到已记录的想法（可删可改） */}
          {step === "outline" || step === "done" ? (
            <IdeaChips ideas={ideas} onRemove={removeIdea} />
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
