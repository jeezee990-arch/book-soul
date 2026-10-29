/**
 * 开新书向导的**流程编排**（组合三条流 + 计时 + 收尾）。
 *
 * 为什么单独抽这个 hook
 * --------------------
 * `NewBook/index.tsx` 原本把三条流 + 计时 + 跳转全写在组件里，
 * 文件超过 500 行（AGENTS.md §8.1）。现在：
 *
 * - `use-elapsed-timer.ts` —— 计时（三条流共用）
 * - `use-plot-stream.ts` —— 剧情流
 * - `use-outline-stream.ts` —— 大纲流
 * - `use-character-stream.ts` —— 人物卡流
 * - `first-chapter.ts` —— 取第一章（纯函数）
 * - `use-newbook-flow.ts`（本文件）—— 把上面几块拼起来
 * - `index.tsx` —— 只剩渲染 + 想法输入
 *
 * ⚠️ 顺序很重要：人物卡流必须**先**建好，大纲流才能在完成回调里调它。
 */

import { useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { chaptersApi } from "@/api/chapters";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useNewBookStore } from "@/stores/newbook-store";
import { EMPTY_CHAR_PROGRESS } from "./types";
import { firstChapterOf } from "./first-chapter";
import { useElapsedTimer } from "./use-elapsed-timer";
import { usePlotStream } from "./use-plot-stream";
import { useOutlineStream } from "./use-outline-stream";
import { useCharacterStream } from "./use-character-stream";
import { abortChar, abortOutline, abortPlot } from "./stream-abort";

/** 流程编排对外接口。 */
export interface NewBookFlow {
  /** 已耗时秒数（渲染用）。 */
  elapsedSec: number;
  /** 生成 3 个剧情版本。 */
  startPlotStream: () => Promise<void>;
  /** 停止剧情生成。 */
  stopPlotStream: () => void;
  /** 生成大纲（显式传剧情版本下标，避免读到陈旧 state）。 */
  startOutlineStream: (targetIdx?: number | null) => Promise<void>;
  /** 从大纲生成人物卡。 */
  startCharacterStream: (
    novelId: number,
    outline: Record<string, unknown>,
  ) => Promise<void>;
  /** 大纲阶段 → 退回剧情页重选。 */
  handleBackToPlot: () => void;
  /** 完成 → 自动建第一章 → 跳写作页。 */
  handleFinish: () => Promise<void>;
  /** 回到种子页（中止所有在跑的生成）。 */
  handleBackToSeed: () => void;
}

/**
 * 开新书向导的流程编排。
 *
 * @returns 流程控制接口
 */
export function useNewBookFlow(): NewBookFlow {
  const navigate = useNavigate();
  const refreshNovels = useNovelsStore((s) => s.refresh);
  const setTarget = useWorkspaceStore((s) => s.setTarget);

  const setStep = useNewBookStore((s) => s.setStep);
  const setOutlinePartial = useNewBookStore((s) => s.setOutlinePartial);
  const setOutlineChaptersDone = useNewBookStore((s) => s.setOutlineChaptersDone);
  const setOutlineThinking = useNewBookStore((s) => s.setOutlineThinking);
  const setOutlineMeta = useNewBookStore((s) => s.setOutlineMeta);
  const setOutlineStats = useNewBookStore((s) => s.setOutlineStats);
  const setOutlinePhase = useNewBookStore((s) => s.setOutlinePhase);
  const setCharProgress = useNewBookStore((s) => s.setCharProgress);
  const setCharThinking = useNewBookStore((s) => s.setCharThinking);
  const setCharStats = useNewBookStore((s) => s.setCharStats);

  const timer = useElapsedTimer();
  const { stopElapsed } = timer;

  // ⚠️ 顺序：人物卡流先建，大纲流的完成回调才能拿到它。
  //
  // 用 ref 固定回调身份：否则每次渲染都传一个新函数下去，
  // 大纲流的 useCallback 依赖它 → 每次渲染都重建 → 白白生成新闭包。
  const character = useCharacterStream(timer);
  const charStartRef = useRef(character.startCharacterStream);
  charStartRef.current = character.startCharacterStream;
  const handleOutlineDone = useCallback(
    (novelId: number, structure: Record<string, unknown>) => {
      void charStartRef.current(novelId, structure);
    },
    [],
  );

  const outline = useOutlineStream(timer, handleOutlineDone);
  const plot = usePlotStream(timer);

  /**
   * 大纲阶段 → 退回剧情页重选（不然选错一条只能整本重开）。
   */
  const handleBackToPlot = useCallback(() => {
    abortOutline();
    abortChar();
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
  }, [
    setStep,
    setOutlinePartial,
    setOutlineChaptersDone,
    setOutlineThinking,
    setOutlineMeta,
    setOutlineStats,
    setOutlinePhase,
    setCharProgress,
    setCharThinking,
    setCharStats,
  ]);

  /**
   * 完成 → 自动建第一章 → 跳写作页。
   *
   * 消除"到了创作页还要再点新建章节"的二次断点。
   */
  const handleFinish = useCallback(async () => {
    const outlineMeta = useNewBookStore.getState().outlineMeta;
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
  }, [setTarget, refreshNovels, navigate]);

  /**
   * 回到种子页 —— 中止所有在跑的生成。
   *
   * ⚠️ 中止后必须**停掉计时**，否则秒数会一直往上跳
   *    （abort 触发的 finally 也会停，但那条路只在"正在流式"时存在）。
   */
  const handleBackToSeed = useCallback(() => {
    abortPlot();
    abortOutline();
    abortChar();
    stopElapsed();
    setStep("seed");
  }, [setStep, stopElapsed]);

  return {
    elapsedSec: timer.elapsedSec,
    startPlotStream: plot.startPlotStream,
    stopPlotStream: plot.stopPlotStream,
    startOutlineStream: outline.startOutlineStream,
    startCharacterStream: character.startCharacterStream,
    handleBackToPlot,
    handleFinish,
    handleBackToSeed,
  };
}
