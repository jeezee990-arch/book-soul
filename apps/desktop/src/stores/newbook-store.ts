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
import {
  DEFAULT_OUTLINE_SCALE,
  type OutlineScale,
} from "@/lib/outline-scale";

/** 向导步骤。 */
export type NewBookStep = "seed" | "plot" | "outline" | "done";

/** 某一卷的细化状态（阶段二）。 */
export type OutlineVolumeStatus = "running" | "done" | "error";

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
  /**
   * 大纲规模（总章数 / 每卷章数 / 每章字数）。
   *
   * ⚠️ 2026-10-25 新增：以前规模写死在 prompt 里（20-40 章），作者写的
   *    "100 章"被无视。现在是显式参数，会随请求发给后端。
   */
  outlineScale: OutlineScale;
  /**
   * 作者是否**手动**改过规模。
   *
   * 用来决定"想法里识别到新数字"时要不要自动覆盖 ——
   * 作者手填的值不该被自动识别冲掉。
   */
  outlineScaleTouched: boolean;
  /** 已生成的大纲（作品 id + 结构） */
  outlineMeta: NovelState | null;
  /**
   * 本次向导建出来的**书名**（2026-10-25 新增）。
   *
   * ⚠️ 为什么要单独存：后端按书名 upsert 作品（同名 → 复用同一本）。
   *    不传书名的话，后端会生成唯一名 —— 那么"退回剧情页再生成一次"
   *    就会**新建第二本书**，第一次的那本变成孤儿。
   *    存下来后：同一向导内重生成 → 复用同一本；换一本 → 「再写一本」清空。
   */
  novelName: string | null;
  /**
   * 本次向导建出来的**作品 id**（2026-10-30 新增）。
   *
   * ⚠️ 为什么要 id 而不是只靠名字：以前"重生成同一本"靠**名字**识别，
   *    而名字会撞车 —— 素材库里已经有一本《修仙新作》时，新书会被
   *    合并进旧书（旧书大纲被冲掉，新书存不进素材库）。
   *    改成靠 **id** 区分：
   *    - 有 id → 复用这一本（重生成）
   *    - 无 id → 新建一本（名字自动避让重名）
   */
  novelId: number | null;
  /**
   * 作者在第一步输入的**书名**（2026-10-30 新增）。
   *
   * 留空 = 让程序自动命名（``题材新作``，撞名自动加序号）。
   */
  novelTitleInput: string;
  /**
   * 上次生成时**实际生效**的书名（2026-10-30 新增）。
   *
   * 用来区分"作者改过名字"和"名字没动"：
   * 只有作者**主动改过**才把新名字发给后端。
   * 否则用户在素材库里给这本书改过名后，回到向导一重新生成，
   * 名字会被悄悄改回旧名（作者在别处的改动被覆盖）。
   */
  novelTitleApplied: string;
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
  /**
   * 卷下标 → 阶段二细化状态（2026-10-25 两阶段大纲）。
   *
   * 骨架阶段结束后，各卷**并行**补细节 —— 用户要能看到"哪一卷好了"。
   */
  outlineVolumeStatus: Record<number, OutlineVolumeStatus>;
  /** 大纲阶段的思考文本 */
  outlineThinking: string;
  /** 人物卡阶段的思考文本 */
  charThinking: string;
  /** 大纲步骤内部阶段 */
  outlinePhase: "outline" | "characters" | "done";
  /**
   * 大纲是否正在生成（**不持久化**）。
   *
   * 用途：刷新页面后用它区分"正在生成"与"上次生成被刷新打断了" ——
   * 后者要给出明确提示，而不是永远转圈。
   */
  outlineBusy: boolean;
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
  /** 设置大纲规模（并标记为"手动改过"） */
  setOutlineScale: (scale: OutlineScale) => void;
  /**
   * 自动填充规模（从想法里识别出来的）。
   *
   * 已经手动改过就**不覆盖** —— 返回 true 表示确实填了。
   */
  autoFillOutlineScale: (scale: OutlineScale) => boolean;
  /** 取消"手动改过"标记（下次自动识别可以覆盖了） */
  resetOutlineScaleTouched: () => void;
  setOutlineMeta: (meta: NovelState | null) => void;
  /** 记录本次向导建出来的书名（重生成时复用同一本作品） */
  setNovelName: (name: string | null) => void;
  /** 记录本次向导建出来的作品 id（重生成时复用同一本作品） */
  setNovelId: (id: number | null) => void;
  /** 记录作者输入的书名（留空 = 自动命名） */
  setNovelTitleInput: (title: string) => void;
  /** 记录上次生成时实际生效的书名 */
  setNovelTitleApplied: (title: string) => void;
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
  setOutlinePartial: (
    s:
      | Record<string, unknown>
      | null
      | ((prev: Record<string, unknown> | null) => Record<string, unknown> | null),
  ) => void;
  setOutlineChaptersDone: (n: number) => void;
  /** 设置各卷细化状态（支持函数式更新） */
  setOutlineVolumeStatus: (
    s:
      | Record<number, OutlineVolumeStatus>
      | ((prev: Record<number, OutlineVolumeStatus>) => Record<number, OutlineVolumeStatus>),
  ) => void;
  setOutlineThinking: (t: string | ((prev: string) => string)) => void;
  setCharThinking: (t: string | ((prev: string) => string)) => void;
  setOutlinePhase: (p: "outline" | "characters" | "done") => void;
  /** 大纲是否正在生成（不持久化） */
  setOutlineBusy: (busy: boolean) => void;
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
        outlineScale: DEFAULT_OUTLINE_SCALE,
        outlineScaleTouched: false,
        outlineMeta: null,
        novelName: null,
        novelId: null,
        novelTitleInput: "",
        novelTitleApplied: "",
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
        outlineVolumeStatus: {},
        outlineThinking: "",
        charThinking: "",
        outlinePhase: "outline",
        outlineBusy: false,
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
        setOutlineScale: (outlineScale) =>
          set({ outlineScale, outlineScaleTouched: true }),
        autoFillOutlineScale: (outlineScale) => {
          let filled = false;
          set((s) => {
            if (s.outlineScaleTouched) return s;
            filled = true;
            return { ...s, outlineScale };
          });
          return filled;
        },
        resetOutlineScaleTouched: () => set({ outlineScaleTouched: false }),
        setOutlineMeta: (outlineMeta) => set({ outlineMeta }),
        setNovelName: (novelName) => set({ novelName }),
        setNovelId: (novelId) => set({ novelId }),
        setNovelTitleInput: (novelTitleInput) => set({ novelTitleInput }),
        setNovelTitleApplied: (novelTitleApplied) => set({ novelTitleApplied }),
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
        setOutlinePartial: (outlinePartial) =>
          set((s) => ({
            outlinePartial:
              typeof outlinePartial === "function"
                ? outlinePartial(s.outlinePartial)
                : outlinePartial,
          })),
        setOutlineChaptersDone: (outlineChaptersDone) =>
          set({ outlineChaptersDone }),
        setOutlineVolumeStatus: (outlineVolumeStatus) =>
          set((s) => ({
            outlineVolumeStatus:
              typeof outlineVolumeStatus === "function"
                ? outlineVolumeStatus(s.outlineVolumeStatus)
                : outlineVolumeStatus,
          })),
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
        setOutlineBusy: (outlineBusy) => set({ outlineBusy }),
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
            outlineScale: DEFAULT_OUTLINE_SCALE,
            outlineScaleTouched: false,
            outlineMeta: null,
            novelName: null,
            novelId: null,
            novelTitleInput: "",
            novelTitleApplied: "",
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
            outlineVolumeStatus: {},
            outlineThinking: "",
            charThinking: "",
            outlinePhase: "outline",
            outlineBusy: false,
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
          outlineScale: s.outlineScale,
          outlineScaleTouched: s.outlineScaleTouched,
          // ⚠️ outlinePhase 必须持久化：否则刷新后回到 "outline"，
          //    而 outlinePartial 不持久化 → 页面永远停在"正在生成大纲"死界面
          //    （2026-10-25 巡检发现）。
          outlinePhase: s.outlinePhase,
          outlineMeta: s.outlineMeta,
          novelName: s.novelName,
          novelId: s.novelId,
          novelTitleInput: s.novelTitleInput,
          novelTitleApplied: s.novelTitleApplied,
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
