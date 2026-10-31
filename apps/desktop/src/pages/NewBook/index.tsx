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
 * ⚠️ 本文件只负责**渲染 + 想法输入**；三条流的实现在
 *    `use-plot-stream.ts` / `use-outline-stream.ts` / `use-character-stream.ts`，
 *    编排见 `use-newbook-flow.ts`（AGENTS.md §8.1：单文件 ≤ 500 行）。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useNewBookStore, type NewBookStep } from "@/stores/newbook-store";
import SeedStep from "./seed-step";
import PlotStep from "./plot-step";
import OutlineStep from "./outline-step";
import OutlineModePicker from "./outline-mode-picker";
import OutlineScaleBar from "./outline-scale-bar";
import IdeaChips from "./idea-chips";
import { parseScaleFromText } from "@/lib/outline-scale";
import { useNewBookFlow } from "./use-newbook-flow";
import { cn } from "@/lib/utils";

const STEPS: { key: NewBookStep; label: string }[] = [
  { key: "seed", label: "种子" },
  { key: "plot", label: "剧情" },
  { key: "outline", label: "大纲与人物" },
];

export default function NewBook() {
  const navigate = useNavigate();

  // ===== 持久化进度（切页面回来还在）=====
  const step = useNewBookStore((s) => s.step);
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
  const charProgress = useNewBookStore((s) => s.charProgress);
  const plotStats = useNewBookStore((s) => s.plotStats);
  const outlineStats = useNewBookStore((s) => s.outlineStats);
  const charStats = useNewBookStore((s) => s.charStats);
  const resetAll = useNewBookStore((s) => s.resetAll);

  // ===== 命名（2026-10-30）=====
  /** 作者输入的书名（留空 = 自动命名） */
  const novelTitleInput = useNewBookStore((s) => s.novelTitleInput);
  const setNovelTitleInput = useNewBookStore((s) => s.setNovelTitleInput);
  /** 已经建出来的那本书（重生成时靠它复用，不再新建） */
  const novelId = useNewBookStore((s) => s.novelId);
  /** 那本书的名字（重名提示时要排除它自己） */
  const novelName = useNewBookStore((s) => s.novelName);

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
  /** 大纲 + 人物 */
  /** 流式过程中已解析出的**部分**大纲结构（不是原始 JSON 文本） */
  const outlinePartial = useNewBookStore((s) => s.outlinePartial);
  const setOutlinePartial = useNewBookStore((s) => s.setOutlinePartial);
  /** 流式过程中已完成的章节数 */
  const outlineChaptersDone = useNewBookStore((s) => s.outlineChaptersDone);
  const setOutlineChaptersDone = useNewBookStore((s) => s.setOutlineChaptersDone);
  /** 各卷细化状态（阶段二并行补细节时显示"哪一卷好了"） */
  const outlineVolumeStatus = useNewBookStore((s) => s.outlineVolumeStatus);
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

  // ===== 流程（三条流 + 计时 + 收尾）=====
  const flow = useNewBookFlow();
  const { elapsedSec } = flow;

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
                title={novelTitleInput}
                onTitleChange={setNovelTitleInput}
                excludeName={novelId !== null ? novelName : null}
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
                  onClick={() => void flow.startPlotStream()}
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
                onStop={flow.stopPlotStream}
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
                      onClick={flow.handleBackToSeed}
                      className="h-9 rounded-lg px-4 text-[13px] text-neutral-500 transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800"
                    >
                      ← 回到种子
                    </button>
                    <button
                      type="button"
                      onClick={() => void flow.startOutlineStream(chosenPlotIdx)}
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
                    onClick={flow.handleBackToSeed}
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
              onFinish={() => void flow.handleFinish()}
              onBack={flow.handleBackToPlot}
              onRestart={() => {
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
