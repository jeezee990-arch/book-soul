/** 灵感园（Phase 4 重写版）。
 *
 * 设计（按 JEE 任务 3+4 重构）：
 * - 主区域是一个状态机：idle → seed → plot_stream → plot_review → outline_stream → character_stream → done
 * - 底部 ChatInput 一直保留（任务 4：作者想法作为 user_extra 随每个 LLM 请求发送）
 * - 种子（题材 + 关键词）只在内存中；用户切走/不继续就丢（不持久化）
 * - 不展示过去灵感；只展示当前创作状态。
 * - 所有 LLM 输出流式渲染（任务 1）
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import { outlinesApi } from "@/api/outlines";
import { charactersApi } from "@/api/characters";
import { wordbanksApi } from "@/api/wordbanks";
import { readNdjsonStream, type StreamRequest } from "@/api/streams";
import { GENRE_PRIORITY, type GenreDef } from "@/config/genres";
import { Button } from "@/components/ui/button";
import ChatInput from "@/components/ChatInput";

type Step = "idle" | "seed" | "plot_stream" | "plot_review" | "outline_stream" | "character_stream" | "done";

interface PlotVersion {
  index: number;
  summary: string;
}

interface NovelState {
  id: number;
  name: string;
  outlineStructure: Record<string, unknown>;
}

export default function Inspiration() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("idle");

  // 种子（内存，不持久化）
  const [genre, setGenre] = useState<GenreDef | null>(null);
  const [keywords, setKeywords] = useState<Set<string>>(new Set());

  // 剧情流
  const [plotVersions, setPlotVersions] = useState<PlotVersion[]>([]);
  const [plotStreaming, setPlotStreaming] = useState<Record<number, string>>({});
  const [chosenPlotIdx, setChosenPlotIdx] = useState<number | null>(null);
  const plotAbortRef = useRef<AbortController | null>(null);

  // 大纲流
  const [outlineText, setOutlineText] = useState("");
  const [outlineMeta, setOutlineMeta] = useState<NovelState | null>(null);
  const outlineAbortRef = useRef<AbortController | null>(null);

  // 人物流
  const [charProgress, setCharProgress] = useState<{
    extracted: { name: string; role: string }[];
    cards: { name: string; role: string; id?: number; text: string }[];
    error?: string;
  }>({ extracted: [], cards: [] });
  const charAbortRef = useRef<AbortController | null>(null);

  // 底部作者想法（累积；随请求发送）
  const [userExtra, setUserExtra] = useState("");
  const [userExtraSending, setUserExtraSending] = useState(false);

  // ===== 流程切换 =====

  const goSeed = useCallback(() => {
    setPlotVersions([]);
    setPlotStreaming({});
    setChosenPlotIdx(null);
    setOutlineText("");
    setOutlineMeta(null);
    setCharProgress({ extracted: [], cards: [] });
    setStep("seed");
  }, []);

  const goIdle = useCallback(() => {
    // 用户离开 / 不继续 → 种子丢弃
    setGenre(null);
    setKeywords(new Set());
    setPlotVersions([]);
    setPlotStreaming({});
    setChosenPlotIdx(null);
    setOutlineText("");
    setOutlineMeta(null);
    setCharProgress({ extracted: [], cards: [] });
    setUserExtra("");
    setStep("idle");
  }, []);

  // ===== 步骤 1+2：选择题材 + 关键词（合并）=====

  const toggleSelectedKeyword = useCallback((kw: string) => {
    setKeywords((prev) => {
      const next = new Set(prev);
      if (next.has(kw)) next.delete(kw);
      else next.add(kw);
      return next;
    });
  }, []);

  const removeKeyword = useCallback((kw: string) => {
    setKeywords((prev) => {
      const next = new Set(prev);
      next.delete(kw);
      return next;
    });
  }, []);

  const removeKeywords = useCallback((kws: string[]) => {
    if (kws.length === 0) return;
    setKeywords((prev) => {
      const next = new Set(prev);
      kws.forEach((k) => next.delete(k));
      return next;
    });
  }, []);

  const startPlotStream = useCallback(async () => {
    if (!genre || keywords.size === 0) return;
    setPlotVersions([]);
    setPlotStreaming({});
    setChosenPlotIdx(null);
    setStep("plot_stream");
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
        const event = obj.event as string | undefined;
        const text = obj.text as string | undefined;
        const index = obj.index as number | undefined;
        if (event === "version_start") {
          setPlotStreaming((s) => ({ ...s, [index!]: "" }));
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
        } else if (event === "error") {
          toast.error("剧情生成失败", {
            description: (obj.message as string) ?? "未知错误",
          });
          setStep("plot_review");
          return;
        } else if (event === "done") {
          // 全部完成
        }
      }
      setStep("plot_review");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("abort")) return;
      toast.error("剧情生成中断", { description: msg });
      setStep("plot_review");
    }
  }, [genre, keywords, userExtra]);

  // ===== 步骤 3：选剧情 → 大纲 =====

  const startOutlineStream = useCallback(async () => {
    if (chosenPlotIdx === null) return;
    const plot = plotVersions.find((v) => v.index === chosenPlotIdx);
    if (!plot) return;
    setOutlineText("");
    setOutlineMeta(null);
    setStep("outline_stream");
    const ctrl = new AbortController();
    outlineAbortRef.current = ctrl;
    const req: StreamRequest = outlinesApi.generateStream(
      {
        genre: genre?.name ?? "通用",
        plot_summary: plot.summary,
        keywords: Array.from(keywords),
        novel_name: undefined,
        outline_type: "complete",
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
        const event = obj.event as string | undefined;
        if (event === "delta") {
          const t = obj.text as string | undefined;
          if (t) setOutlineText((s) => s + t);
        } else if (event === "done") {
          setOutlineMeta({
            id: obj.novel_id as number,
            name: (obj.novel_name as string) ?? "",
            outlineStructure: (obj.structure as Record<string, unknown>) ?? {},
          });
          setStep("character_stream");
          // 自动触发人物卡生成
          void startCharacterStream(
            obj.novel_id as number,
            obj.structure as Record<string, unknown>,
          );
        } else if (event === "error") {
          toast.error("大纲生成失败", {
            description: (obj.message as string) ?? "未知错误",
          });
          setStep("plot_review");
          return;
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("abort")) return;
      toast.error("大纲生成中断", { description: msg });
      setStep("plot_review");
    }
  }, [chosenPlotIdx, plotVersions, genre, keywords, userExtra]);

  // ===== 步骤 4：人物卡生成 =====

  const startCharacterStream = useCallback(
    async (novelId: number, outline: Record<string, unknown>) => {
      setCharProgress({ extracted: [], cards: [] });
      const ctrl = new AbortController();
      charAbortRef.current = ctrl;
      const req: StreamRequest = charactersApi.generateFromOutlineStream(
        novelId,
        {
          outline,
          genre: genre?.name ?? "通用",
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
          const event = obj.event as string | undefined;
          if (event === "phase") continue;
          if (event === "extract_delta") {
            // 抽取阶段文本（暂时不展示，但累计不影响主流程）
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
          } else if (event === "error") {
            setCharProgress((s) => ({ ...s, error: obj.message as string }));
          } else if (event === "done") {
            setStep("done");
            toast.success(`已生成 ${(obj.saved_count as number) ?? 0} 个人物卡`);
          }
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (msg.includes("abort")) return;
        toast.error("人物卡生成中断", { description: msg });
      }
    },
    [genre, userExtra],
  );

  // ===== 离开页面 → 取消未完成请求 =====
  useEffect(() => {
    return () => {
      plotAbortRef.current?.abort();
      outlineAbortRef.current?.abort();
      charAbortRef.current?.abort();
    };
  }, []);

  // ===== 底部输入：同时作 user_extra + 关键词 =====
  const handleUserExtraSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      // 永远累加到 user_extra（影响所有后续 LLM prompt）
      setUserExtra((prev) => (prev ? prev + "\n" + trimmed : trimmed));
      // seed 步骤额外把文本加到关键词（用户希望"输入即词条"）
      if (step === "seed") {
        setKeywords((prev) => {
          if (prev.has(trimmed)) return prev;
          const next = new Set(prev);
          next.add(trimmed);
          return next;
        });
        toast.success(`已加入关键词：${trimmed.length > 30 ? trimmed.slice(0, 30) + "…" : trimmed}`);
      } else {
        setUserExtraSending(true);
        setTimeout(() => setUserExtraSending(false), 300);
        toast.info("想法已记录，下次生成时随 prompt 发送", {
          description: trimmed.length > 30 ? `${trimmed.slice(0, 30)}…` : trimmed,
        });
      }
    },
    [step],
  );

  // ===== UI 渲染 =====

  const chatPlaceholder = useMemo(() => {
    switch (step) {
      case "seed":
        return "描述你想要的剧情氛围 / 主角特点 / 题材混搭…（点发送即记录）";
      case "plot_stream":
        return "对剧情的补充想法（生成中…）";
      case "plot_review":
        return "对剧情的修改意见（点发送即记录）";
      case "outline_stream":
        return "对大纲的调整意见（生成中…）";
      case "character_stream":
        return "对人物的特别要求（生成中…）";
      case "done":
        return "（已完成；后续可去创作页继续）";
      default:
        return "输入消息... (输入 / 唤起命令)";
    }
  }, [step]);

  return (
    <>
      {step === "idle" && (
        <WelcomeView onStart={goSeed} />
      )}

      {step === "seed" && (
        <SeedView
          genre={genre}
          onSelectGenre={setGenre}
          keywords={keywords}
          onToggleKeyword={toggleSelectedKeyword}
          onRemoveKeyword={removeKeyword}
          onRemoveKeywords={removeKeywords}
          onGenerate={startPlotStream}
          onBack={goIdle}
        />
      )}

      {(step === "plot_stream" || step === "plot_review") && (
        <PlotStreamView
          genre={genre}
          keywords={keywords}
          versions={plotVersions}
          streaming={plotStreaming}
          isStreaming={step === "plot_stream"}
          chosenIdx={chosenPlotIdx}
          onChoose={(idx) => {
            setChosenPlotIdx(idx);
            if (step === "plot_review") void startOutlineStream();
          }}
          onBack={() => {
            plotAbortRef.current?.abort();
            setStep("seed");
          }}
          userExtra={userExtra}
        />
      )}

      {step === "outline_stream" && (
        <OutlineStreamView
          text={outlineText}
          onBack={() => {
            outlineAbortRef.current?.abort();
            setStep("plot_review");
          }}
        />
      )}

      {step === "character_stream" && (
        <CharacterStreamView
          progress={charProgress}
          novelMeta={outlineMeta}
          onBack={() => {
            charAbortRef.current?.abort();
            setStep("plot_review");
          }}
        />
      )}

      {step === "done" && outlineMeta && (
        <DoneView
          novelMeta={outlineMeta}
          charCount={charProgress.cards.filter((c) => c.id).length}
          onCreateChapters={() => navigate("/creation")}
          onRestart={goIdle}
        />
      )}

      {step !== "idle" && (
        <ChatInput
          placeholder={chatPlaceholder}
          disabled={userExtraSending}
          onSubmit={handleUserExtraSubmit}
        />
      )}
    </>
  );
}

// ===== 子视图 =====

function WelcomeView({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-8">
      <div className="space-y-6">
        <div className="w-20 h-20 mx-auto rounded-full bg-neutral-100 dark:bg-neutral-900 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-9 h-9 text-neutral-700 dark:text-neutral-300"
          >
            <path
              d="M12 6.5v13M5 4.5h6.5a2 2 0 012 2v13a2 2 0 00-2-2H5a2 2 0 01-2-2v-9a2 2 0 012-2zM19 4.5h-6.5a2 2 0 00-2 2v13a2 2 0 012-2H19a2 2 0 002-2v-9a2 2 0 00-2-2z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">
          Book Soul，让创作更快捷
        </h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400 max-w-md mx-auto">
          从一句话种子到一部作品。AI 帮你跑通题材 → 词库 → 剧情 → 大纲 → 人物 → 章节的完整链路。
        </p>
      </div>
      <Button size="lg" onClick={onStart}>
        开始创作 →
      </Button>
    </div>
  );
}

function SeedView({
  genre,
  onSelectGenre,
  keywords,
  onToggleKeyword,
  onRemoveKeyword,
  onRemoveKeywords,
  onGenerate,
  onBack,
}: {
  genre: GenreDef | null;
  onSelectGenre: (g: GenreDef | null) => void;
  keywords: Set<string>;
  onToggleKeyword: (kw: string) => void;
  onRemoveKeyword: (kw: string) => void;
  onRemoveKeywords: (kws: string[]) => void;
  onGenerate: () => void;
  onBack: () => void;
}) {
  // 题材的 wordbank categories（meta）
  const [categories, setCategories] = useState<string[]>([]);
  // 当前展示的候选池
  const [candidates, setCandidates] = useState<string[]>([]);
  // 加载态
  const [loading, setLoading] = useState(false);
  // 批量管理模式
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkSelected, setBulkSelected] = useState<Set<string>>(new Set());

  // 取 meta + 首批候选（按 genre 变化时拉）
  const fetchInitial = useCallback(async (g: GenreDef) => {
    setLoading(true);
    try {
      const meta = await wordbanksApi.getMeta(g.id);
      const cats = meta.categories;
      setCategories(cats);
      // 拉首批（每个分类拿 2 个，避免重复 + 已选）
      const words = await fetchRandomBatch(g.id, cats, 10, new Set());
      setCandidates(words);
    } catch (e) {
      toast.error("加载词库失败", {
        description: e instanceof Error ? e.message : String(e),
      });
      setCandidates([]);
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (genre) {
      void fetchInitial(genre);
    } else {
      setCandidates([]);
      setCategories([]);
    }
  }, [genre, fetchInitial]);

  // 刷新词条（拉新一批，已选保留，已选在池中保留可见）
  const refresh = useCallback(async () => {
    if (!genre) return;
    setLoading(true);
    try {
      const words = await fetchRandomBatch(
        genre.id,
        categories.length > 0 ? categories : [],
        10,
        keywords,
      );
      setCandidates(words);
    } catch (e) {
      toast.error("刷新词条失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setLoading(false);
    }
  }, [genre, categories, keywords]);

  // 批量删除
  const handleBulkDelete = useCallback(() => {
    if (bulkSelected.size === 0) return;
    onRemoveKeywords(Array.from(bulkSelected));
    setBulkSelected(new Set());
    setBulkMode(false);
    toast.success(`已删除 ${bulkSelected.size} 个词条`);
  }, [bulkSelected, onRemoveKeywords]);

  const toggleBulkOne = useCallback((kw: string) => {
    setBulkSelected((prev) => {
      const next = new Set(prev);
      if (next.has(kw)) next.delete(kw);
      else next.add(kw);
      return next;
    });
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">选题材 + 关键词</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            选好后点"生成 3 个剧情"会自动进入下一步
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 返回
        </Button>
      </header>

      {/* 题材选择 */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">题材</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {GENRE_PRIORITY.map((g) => (
            <button
              key={g.id}
              onClick={() => onSelectGenre(g)}
              className={`flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg border text-sm transition-all ${
                genre?.id === g.id
                  ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300"
                  : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700"
              }`}
            >
              <span>{g.emoji}</span>
              <span>{g.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 已选取词条 */}
      {genre && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
              已选取词条（{keywords.size}）
            </p>
            {keywords.size > 0 && (
              <button
                onClick={() => {
                  if (bulkMode && bulkSelected.size > 0) {
                    handleBulkDelete();
                  } else {
                    setBulkMode((v) => !v);
                    setBulkSelected(new Set());
                  }
                }}
                className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                  bulkMode && bulkSelected.size > 0
                    ? "bg-red-500 text-white hover:bg-red-600"
                    : "text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                }`}
              >
                {bulkMode && bulkSelected.size > 0
                  ? `删除选中 (${bulkSelected.size})`
                  : bulkMode
                    ? "退出批量"
                    : "批量管理"}
              </button>
            )}
          </div>

          {keywords.size === 0 ? (
            <p className="text-xs text-neutral-400 italic">还未选取词条；可以从下方候选池点选，或在底部输入框输入</p>
          ) : (
            <div className="flex flex-wrap gap-2 min-h-[2.5rem] p-3 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/40">
              {Array.from(keywords).map((kw) => {
                const isBulkSelected = bulkSelected.has(kw);
                const isFromCandidates = candidates.includes(kw);
                return (
                  <div
                    key={kw}
                    className={`group inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full text-sm border transition-all ${
                      isBulkSelected
                        ? "border-red-400 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300"
                        : isFromCandidates
                          ? "border-neutral-700 bg-neutral-700 text-white dark:border-neutral-300 dark:bg-neutral-300 dark:text-neutral-900"
                          : "border-indigo-300 bg-indigo-50 dark:border-indigo-700 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300"
                    }`}
                  >
                    {bulkMode && (
                      <button
                        type="button"
                        onClick={() => toggleBulkOne(kw)}
                        className="w-3.5 h-3.5 rounded-sm border flex items-center justify-center"
                        aria-label="选择"
                      >
                        {isBulkSelected && (
                          <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-red-600">
                            <path d="M2 6l3 3 5-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </button>
                    )}
                    <span>{kw}</span>
                    {!bulkMode && (
                      <button
                        type="button"
                        onClick={() => onRemoveKeyword(kw)}
                        className="w-5 h-5 rounded-full flex items-center justify-center opacity-60 hover:opacity-100 hover:bg-black/10 dark:hover:bg-white/10"
                        aria-label="删除"
                      >
                        <svg viewBox="0 0 12 12" className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 3l6 6m0-6l-6 6" strokeLinecap="round" />
                        </svg>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 候选池（可刷新） */}
      {genre && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
              关键词（候选池，点选加入已选）
            </p>
            <button
              onClick={refresh}
              disabled={loading || categories.length === 0}
              className="text-xs px-2.5 py-1 rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1"
              aria-label="刷新词条"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
              >
                <path d="M21 12a9 9 0 11-3-6.7M21 3v6h-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              刷新词条
            </button>
          </div>
          <div className="flex flex-wrap gap-2 min-h-[2.5rem] p-3 rounded-lg border border-dashed border-neutral-200 dark:border-neutral-800">
            {loading && candidates.length === 0 ? (
              <p className="text-xs text-neutral-400">加载中…</p>
            ) : candidates.length === 0 ? (
              <p className="text-xs text-neutral-400 italic">暂无候选词条；可点上方"刷新词条"换一批</p>
            ) : (
              candidates.map((kw) => {
                const isSelected = keywords.has(kw);
                return (
                  <button
                    key={kw}
                    onClick={() => onToggleKeyword(kw)}
                    className={`px-3 py-1.5 rounded-full text-sm border transition-all ${
                      isSelected
                        ? "border-neutral-700 bg-neutral-700 text-white dark:border-neutral-300 dark:bg-neutral-300 dark:text-neutral-900"
                        : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700"
                    }`}
                  >
                    {kw}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* 操作 */}
      <div className="flex items-center justify-end pt-4">
        <Button
          onClick={onGenerate}
          disabled={!genre || keywords.size === 0}
        >
          生成 3 个剧情 →
        </Button>
      </div>
    </div>
  );
}

/** 从 wordbank API 拉一批随机词（多分类合并、去重、避开已选）。 */
async function fetchRandomBatch(
  genreId: string,
  categories: string[],
  n: number,
  exclude: Set<string>,
): Promise<string[]> {
  if (categories.length === 0) return [];
  // 多个分类各取 n 个，merge 后 shuffle
  const results = await Promise.all(
    categories.map((cat) =>
      wordbanksApi.getRandom(genreId, [cat], n).catch(() => []),
    ),
  );
  const merged: string[] = [];
  for (const r of results) {
    if (Array.isArray(r)) merged.push(...r);
    else if (r && typeof r === "object") {
      for (const list of Object.values(r)) merged.push(...list);
    }
  }
  // 去重 + 排除已选
  const seen = new Set<string>();
  const out: string[] = [];
  for (const w of merged) {
    if (exclude.has(w) || seen.has(w)) continue;
    seen.add(w);
    out.push(w);
    if (out.length >= n) break;
  }
  return out;
}

function PlotStreamView({
  genre,
  keywords,
  versions,
  streaming,
  isStreaming,
  chosenIdx,
  onChoose,
  onBack,
  userExtra,
}: {
  genre: GenreDef | null;
  keywords: Set<string>;
  versions: PlotVersion[];
  streaming: Record<number, string>;
  isStreaming: boolean;
  chosenIdx: number | null;
  onChoose: (idx: number) => void;
  onBack: () => void;
  userExtra: string;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">
            {isStreaming ? "正在生成剧情..." : "选择喜欢的剧情"}
          </h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            {genre?.name} · {keywords.size} 个关键词
            {userExtra && " · 含作者想法"}
          </p>
        </div>
        {!isStreaming && (
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← 返回
          </Button>
        )}
      </header>

      <div className="space-y-4">
        {Array.from({ length: 3 }, (_, i) => i + 1).map((idx) => {
          const v = versions.find((x) => x.index === idx);
          const text = v?.summary ?? streaming[idx] ?? "";
          const streamingHere = isStreaming && !v;
          const chosen = chosenIdx === idx;
          return (
            <button
              key={idx}
              onClick={() => text && !streamingHere && onChoose(idx)}
              disabled={streamingHere || !text}
              className={`w-full text-left rounded-xl border p-5 transition-all ${
                chosen
                  ? "border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20"
                  : streamingHere
                    ? "border-neutral-300 dark:border-neutral-700 animate-pulse"
                    : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-400 dark:hover:border-neutral-600"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-neutral-400">
                  版本 {idx}
                </span>
                {streamingHere && (
                  <span className="text-[10px] text-neutral-400">生成中…</span>
                )}
                {chosen && (
                  <span className="text-xs text-indigo-600 dark:text-indigo-400">
                    ✓ 已选
                  </span>
                )}
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap min-h-[3em]">
                {text || (streamingHere ? "…" : "等待生成…")}
              </p>
            </button>
          );
        })}
      </div>

      {!isStreaming && chosenIdx === null && (
        <p className="text-xs text-neutral-400 text-center">点选一个剧情继续</p>
      )}
    </div>
  );
}

function OutlineStreamView({
  text,
  onBack,
}: {
  text: string;
  onBack: () => void;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">正在生成大纲...</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            解析 + 自动建作品 + 调人物卡...
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 取消
        </Button>
      </header>
      <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-6 min-h-[400px]">
        <pre className="whitespace-pre-wrap text-sm leading-relaxed font-mono">
          {text || "…"}
        </pre>
      </div>
    </div>
  );
}

function CharacterStreamView({
  progress,
  novelMeta,
  onBack,
}: {
  progress: { extracted: { name: string; role: string }[]; cards: { name: string; role: string; id?: number; text: string }[]; error?: string };
  novelMeta: NovelState | null;
  onBack: () => void;
}) {
  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">正在生成人物卡...</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            {novelMeta?.name && `《${novelMeta.name}》`} · 已抽取 {progress.extracted.length} 人
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 取消
        </Button>
      </header>

      <div className="space-y-3">
        {progress.cards.map((c) => (
          <div
            key={c.name}
            className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{c.name}</span>
                <span className="text-xs text-neutral-400">· {c.role}</span>
              </div>
              {c.id !== undefined ? (
                <span className="text-xs text-indigo-600 dark:text-indigo-400">
                  ✓ 已入库 (#{c.id})
                </span>
              ) : (
                <span className="text-xs text-neutral-400 animate-pulse">生成中…</span>
              )}
            </div>
            {c.text && (
              <pre className="text-xs leading-relaxed font-mono whitespace-pre-wrap text-neutral-700 dark:text-neutral-300 max-h-48 overflow-y-auto">
                {c.text}
              </pre>
            )}
          </div>
        ))}
      </div>
      {progress.error && (
        <p className="text-xs text-destructive">{progress.error}</p>
      )}
    </div>
  );
}

function DoneView({
  novelMeta,
  charCount,
  onCreateChapters,
  onRestart,
}: {
  novelMeta: NovelState;
  charCount: number;
  onCreateChapters: () => void;
  onRestart: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center space-y-6">
      <div className="w-16 h-16 mx-auto rounded-full bg-green-100 dark:bg-green-950/30 flex items-center justify-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="w-8 h-8 text-green-600 dark:text-green-400"
        >
          <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">作品《{novelMeta.name}》已就绪</h2>
        <p className="text-sm text-neutral-500">
          1 个大纲 · {charCount} 个人物卡
        </p>
      </div>
      <div className="flex gap-3">
        <Button onClick={onCreateChapters}>去创作章节 →</Button>
        <Button variant="outline" onClick={onRestart}>
          再写一本
        </Button>
      </div>
    </div>
  );
}