/**
 * 开新书向导的进度状态（2026-10-25 新增）。
 *
 * 为什么要有这个 store
 * --------------------
 * 之前整条向导的进度都活在 ``NewBook`` 组件的 ``useState`` 里 ——
 * 组件卸载（切到别的页面）就全没了。用户挑了半天题材、写了 3 条想法、
 * 等出了 3 版剧情，切个页面回来直接回到第一步。
 *
 * 现在把"值得保留的进度"提到全局 store，并持久化到 localStorage：
 * 题材 / 关键词 / 想法词条 / 已生成的剧情 / 大纲 / 人物卡 / 耗时统计。
 *
 * ⚠️ **不持久化**流式中间态（正在吐字的文本、busy 标志）：
 *    那些是瞬时数据，刷新后重新生成一次即可；写进 localStorage 只会
 *    让每次进页面都要 rehydrate 一大坨文本，还可能带着上次的半截内容。
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { GenreDef } from "@/config/genres";
import type { CharProgress, GenStats, NovelState, PlotVersion } from "@/pages/NewBook/types";
import type { OutlineMode } from "@/pages/NewBook/outline-mode-picker";

/** 向导步骤。 */
export type NewBookStep = "seed" | "plot" | "outline" | "done";

interface NewBookState {
  /** 当前步骤 */
  step: NewBookStep;
  /** 选中的题材 */
  genre: GenreDef | null;
  /** 种子关键词 */
  keywords: string[];
  /** 作者想法词条（每次发送加一条） */
  ideas: string[];
  /** 已生成的剧情版本 */
  plotVersions: PlotVersion[];
  /** 选中的剧情版本序号（1 起） */
  chosenPlotIdx: number | null;
  /** 大纲模式（完整 / 半开放式） */
  outlineMode: OutlineMode;
  /** 已生成的大纲（作品 id + 结构） */
  outlineMeta: NovelState | null;
  /** 人物卡进度 */
  charProgress: CharProgress;
  /** 剧情阶段统计 */
  plotStats: GenStats | null;
  /** 大纲阶段统计 */
  outlineStats: GenStats | null;
  /** 人物卡阶段统计 */
  charStats: GenStats | null;

  // ===== 流式中间态（不持久化，但**放在 store 里**）=====
  //
  // ⚠️ 为什么要放在 store 而不是组件的 useState：
  //    组件卸载后 useState 的 setter 调了也没地方存（数据丢了），
  //    而 store 的 set 永远有效 —— 这样"切到别的页面再回来"，
  //    就算生成是在后台继续跑完的，回来也能看到完整结果。

  /** index → 正在流式输出的文本 */
  plotStreaming: Record<number, string>;
  /** index → 模型思考中的文本 */
  plotThinking: Record<number, string>;
  /** index → 该版本的失败原因 */
  plotErrors: Record<number, string>;
  /** 剧情是否正在生成 */
  plotBusy: boolean;
  /** 流式过程中已解析出的部分大纲结构 */
  outlinePartial: Record<string, unknown> | null;
  /** 流式过程中已完成的章节数 */
  outlineChaptersDone: number;
  /** 大纲阶段的思考文本 */
  outlineThinking: string;
  /** 人物卡阶段的思考文本 */
  charThinking: string;
  /** 大纲步骤内部阶段 */
  outlinePhase: "outline" | "characters" | "done";
  /**
   * 本次生成的开始时刻（Date.now()）。
   *
   * ⚠️ 存**时间戳**而不是"已过秒数"：切到别的页面再回来，秒数要能
   *    接着算（用累加值会停在切走的那一刻）。组件里每秒 tick 一次重渲染，
   *    显示值 = (now - elapsedStartedAt) / 1000。
   */
  elapsedStartedAt: number | null;

  // ===== actions =====
  setStep: (step: NewBookStep) => void;
  setGenre: (genre: GenreDef | null) => void;
  toggleKeyword: (kw: string) => void;
  removeKeyword: (kw: string) => void;
  clearKeywords: () => void;
  addIdea: (idea: string) => void;
  removeIdea: (index: number) => void;
  setIdeas: (ideas: string[]) => void;
  /**
   * 设置剧情版本。
   *
   * 支持函数式更新（``(prev) => next``）—— 流式过程中要基于**当前**列表
   * 追加/替换，直接用闭包里的旧值会丢数据。
   */
  setPlotVersions: (
    versions: PlotVersion[] | ((prev: PlotVersion[]) => PlotVersion[]),
  ) => void;
  setChosenPlotIdx: (idx: number | null) => void;
  setOutlineMode: (mode: OutlineMode) => void;
  setOutlineMeta: (meta: NovelState | null) => void;
  /** 设置人物卡进度（同样支持函数式更新） */
  setCharProgress: (
    p: CharProgress | ((prev: CharProgress) => CharProgress),
  ) => void;
  setPlotStats: (s: GenStats | null) => void;
  setOutlineStats: (s: GenStats | null) => void;
  setCharStats: (s: GenStats | null) => void;
  setPlotStreaming: (
    s: Record<number, string> | ((prev: Record<number, string>) => Record<number, string>),
  ) => void;
  setPlotThinking: (
    s: Record<number, string> | ((prev: Record<number, string>) => Record<number, string>),
  ) => void;
  setPlotErrors: (
    s: Record<number, string> | ((prev: Record<number, string>) => Record<number, string>),
  ) => void;
  setPlotBusy: (busy: boolean) => void;
  setOutlinePartial: (s: Record<string, unknown> | null) => void;
  setOutlineChaptersDone: (n: number) => void;
  setOutlineThinking: (t: string | ((prev: string) => string)) => void;
  setCharThinking: (t: string | ((prev: string) => string)) => void;
  setOutlinePhase: (p: "outline" | "characters" | "done") => void;
  setElapsedStartedAt: (t: number | null) => void;
  /** 整个流程重置（「再写一本」） */
  resetAll: () => void;
}

const STORAGE_KEY = "book-soul-newbook";

const EMPTY_CHAR_PROGRESS: CharProgress = { extracted: [], cards: [] };

/**
 * 创建开新书 store。
 *
 * @param storage 可选的持久化后端（测试用内存实现；生产默认 localStorage）
 */
export function createNewBookStore(storage?: StateStorage) {
  return create<NewBookState>()(
    persist(
      (set) => ({
        step: "seed",
        genre: null,
        keywords: [],
        ideas: [],
        plotVersions: [],
        chosenPlotIdx: null,
        outlineMode: "complete",
        outlineMeta: null,
        charProgress: EMPTY_CHAR_PROGRESS,
        plotStats: null,
        outlineStats: null,
        charStats: null,
        plotStreaming: {},
        plotThinking: {},
        plotErrors: {},
        plotBusy: false,
        outlinePartial: null,
        outlineChaptersDone: 0,
        outlineThinking: "",
        charThinking: "",
        outlinePhase: "outline",
        elapsedStartedAt: null,

        setStep: (step) => set({ step }),
        setGenre: (genre) => set({ genre }),
        toggleKeyword: (kw) =>
          set((s) => ({
            keywords: s.keywords.includes(kw)
              ? s.keywords.filter((k) => k !== kw)
              : [...s.keywords, kw],
          })),
        removeKeyword: (kw) =>
          set((s) => ({ keywords: s.keywords.filter((k) => k !== kw) })),
        clearKeywords: () => set({ keywords: [] }),
        addIdea: (idea) =>
          set((s) => ({ ideas: [...s.ideas, idea] })),
        removeIdea: (index) =>
          set((s) => ({ ideas: s.ideas.filter((_, i) => i !== index) })),
        setIdeas: (ideas) => set({ ideas }),
        setPlotVersions: (versions) =>
          set((s) => ({
            plotVersions:
              typeof versions === "function" ? versions(s.plotVersions) : versions,
          })),
        setChosenPlotIdx: (chosenPlotIdx) => set({ chosenPlotIdx }),
        setOutlineMode: (outlineMode) => set({ outlineMode }),
        setOutlineMeta: (outlineMeta) => set({ outlineMeta }),
        setCharProgress: (charProgress) =>
          set((s) => ({
            charProgress:
              typeof charProgress === "function"
                ? charProgress(s.charProgress)
                : charProgress,
          })),
        setPlotStats: (plotStats) => set({ plotStats }),
        setOutlineStats: (outlineStats) => set({ outlineStats }),
        setCharStats: (charStats) => set({ charStats }),
        setPlotStreaming: (plotStreaming) =>
          set((s) => ({
            plotStreaming:
              typeof plotStreaming === "function"
                ? plotStreaming(s.plotStreaming)
                : plotStreaming,
          })),
        setPlotThinking: (plotThinking) =>
          set((s) => ({
            plotThinking:
              typeof plotThinking === "function"
                ? plotThinking(s.plotThinking)
                : plotThinking,
          })),
        setPlotErrors: (plotErrors) =>
          set((s) => ({
            plotErrors:
              typeof plotErrors === "function" ? plotErrors(s.plotErrors) : plotErrors,
          })),
        setPlotBusy: (plotBusy) => set({ plotBusy }),
        setOutlinePartial: (outlinePartial) => set({ outlinePartial }),
        setOutlineChaptersDone: (outlineChaptersDone) =>
          set({ outlineChaptersDone }),
        setOutlineThinking: (outlineThinking) =>
          set((s) => ({
            outlineThinking:
              typeof outlineThinking === "function"
                ? outlineThinking(s.outlineThinking)
                : outlineThinking,
          })),
        setCharThinking: (charThinking) =>
          set((s) => ({
            charThinking:
              typeof charThinking === "function"
                ? charThinking(s.charThinking)
                : charThinking,
          })),
        setOutlinePhase: (outlinePhase) => set({ outlinePhase }),
        setElapsedStartedAt: (elapsedStartedAt) => set({ elapsedStartedAt }),
        resetAll: () =>
          set({
            step: "seed",
            genre: null,
            keywords: [],
            ideas: [],
            plotVersions: [],
            chosenPlotIdx: null,
            outlineMode: "complete",
            outlineMeta: null,
            charProgress: EMPTY_CHAR_PROGRESS,
            plotStats: null,
            outlineStats: null,
            charStats: null,
            plotStreaming: {},
            plotThinking: {},
            plotErrors: {},
            plotBusy: false,
            outlinePartial: null,
            outlineChaptersDone: 0,
            outlineThinking: "",
            charThinking: "",
            outlinePhase: "outline",
            elapsedStartedAt: null,
          }),
      }),
      {
        name: STORAGE_KEY,
        // 只持久化"进度"，不持久化 actions
        partialize: (s) => ({
          step: s.step,
          genre: s.genre,
          keywords: s.keywords,
          ideas: s.ideas,
          plotVersions: s.plotVersions,
          chosenPlotIdx: s.chosenPlotIdx,
          outlineMode: s.outlineMode,
          outlineMeta: s.outlineMeta,
          charProgress: s.charProgress,
          plotStats: s.plotStats,
          outlineStats: s.outlineStats,
          charStats: s.charStats,
        }),
        ...(storage ? { storage: createJSONStorage(() => storage) } : {}),
      },
    ),
  );
}

/** 全局单例（应用里统一用这个）。 */
export const useNewBookStore = createNewBookStore();

export { STORAGE_KEY as NEWBOOK_STORAGE_KEY };
