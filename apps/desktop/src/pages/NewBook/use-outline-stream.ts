/**
 * 大纲生成流（步骤 2 → 3，两阶段）。
 *
 * 阶段一：全书卷章骨架 → 阶段二：各卷并行补细节。
 *
 * ⚠️ AGENTS.md §4.7：思考内容不能丢（后端已净身成纯中文），
 *    里程碑事件（volume_done）保序，失败必须回退到剧情页，
 *    否则界面停在"流式生成中…"永远转圈（§4.10）。
 */

import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { outlinesApi } from "@/api/outlines";
import {
  readNdjsonStream,
  parseOutlineStreamEvent,
  appendThinking,
  type StreamRequest,
} from "@/api/streams";
import { mergeVolumeIntoStructure, fillPendingChapters } from "@/lib/outline-merge";
import { useNewBookStore } from "@/stores/newbook-store";
import { EMPTY_CHAR_PROGRESS } from "./types";
import type { ElapsedTimer } from "./use-elapsed-timer";
import { abortOutline, clearOutlineAbort, setOutlineAbort } from "./stream-abort";

/** 大纲流对外接口。 */
export interface OutlineStreamApi {
  /**
   * 生成大纲。
   *
   * @param targetIdx 显式指定用哪个剧情版本 —— 不传时回退到 store 里的
   *   `chosenPlotIdx`。**必须显式传**（AGENTS.md §4.9）：state 是异步的，
   *   同一帧里读到的还是旧值。
   */
  startOutlineStream: (targetIdx?: number | null) => Promise<void>;
}

/**
 * 大纲生成流。
 *
 * @param timer 共享计时器
 * @param onOutlineDone 大纲完成后的回调（用于自动触发人物卡生成）
 * @returns 流控制接口
 */
export function useOutlineStream(
  timer: ElapsedTimer,
  onOutlineDone: (novelId: number, structure: Record<string, unknown>) => void,
): OutlineStreamApi {
  const { startElapsed, elapsedValueRef } = timer;

  const genre = useNewBookStore((s) => s.genre);
  const keywords = useNewBookStore((s) => s.keywords);
  const ideas = useNewBookStore((s) => s.ideas);
  const outlineMode = useNewBookStore((s) => s.outlineMode);
  const outlineScale = useNewBookStore((s) => s.outlineScale);
  const novelName = useNewBookStore((s) => s.novelName);
  const chosenPlotIdx = useNewBookStore((s) => s.chosenPlotIdx);
  const plotVersions = useNewBookStore((s) => s.plotVersions);
  const setOutlinePartial = useNewBookStore((s) => s.setOutlinePartial);
  const setOutlineChaptersDone = useNewBookStore((s) => s.setOutlineChaptersDone);
  const setOutlineVolumeStatus = useNewBookStore((s) => s.setOutlineVolumeStatus);
  const setOutlineThinking = useNewBookStore((s) => s.setOutlineThinking);
  const setOutlineMeta = useNewBookStore((s) => s.setOutlineMeta);
  const setOutlineStats = useNewBookStore((s) => s.setOutlineStats);
  const setOutlinePhase = useNewBookStore((s) => s.setOutlinePhase);
  const setOutlineBusy = useNewBookStore((s) => s.setOutlineBusy);
  const setCharProgress = useNewBookStore((s) => s.setCharProgress);
  const setCharThinking = useNewBookStore((s) => s.setCharThinking);
  const setCharStats = useNewBookStore((s) => s.setCharStats);
  const setNovelName = useNewBookStore((s) => s.setNovelName);
  const setStep = useNewBookStore((s) => s.setStep);

  /** 发给后端的"作者个人想法"。 */
  const userExtra = useMemo(() => ideas.join("\n"), [ideas]);

  const startOutlineStream = useCallback(
    async (targetIdx?: number | null) => {
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
      setOutlineAbort(ctrl);
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
            onOutlineDone(parsed.novelId, parsed.structure);
          }
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        const aborted = msg.includes("abort");
        if (!aborted) {
          toast.error("大纲生成中断", { description: msg });
        }
        setOutlineBusy(false);
        // ⚠️ 只有**真失败**才退回剧情页。
        //    被 abort（用户点了「← 换一条剧情」/「回到种子」）时不能动步骤 ——
        //    否则这里的 setStep("plot") 会和用户刚点的目标打架，
        //    把用户从「回到种子」又拽回剧情页。
        if (!aborted) {
          setStep("plot");
        }
      } finally {
        clearOutlineAbort(ctrl);
      }
    },
    [
      chosenPlotIdx,
      plotVersions,
      genre,
      keywords,
      userExtra,
      outlineMode,
      outlineScale,
      novelName,
      startElapsed,
      elapsedValueRef,
      onOutlineDone,
      setOutlinePartial,
      setOutlineChaptersDone,
      setOutlineVolumeStatus,
      setOutlineThinking,
      setOutlineMeta,
      setOutlineStats,
      setOutlinePhase,
      setOutlineBusy,
      setCharProgress,
      setCharThinking,
      setCharStats,
      setNovelName,
      setStep,
    ],
  );

  return { startOutlineStream };
}

/** 中断大纲生成（外部用，比如"退回剧情页"）。 */
export function stopOutlineStream(): void {
  abortOutline();
}
