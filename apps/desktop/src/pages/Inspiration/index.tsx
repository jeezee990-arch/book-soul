/** 灵感园（Phase 4 重写版）。
 *
 * 设计（按 JEE 任务 3+4 重构）：
 * - 主区域是一个状态机：idle → seed → plot_stream → plot_review → outline_stream → character_stream → done
 * - 底部 ChatInput 一直保留（任务 4：作者想法作为 user_extra 随每个 LLM 请求发送）
 * - 种子（题材 + 关键词）只在内存中；用户切走/不继续就丢（不持久化）
 * - 不展示过去灵感；只展示当前创作状态。
 * - 所有 LLM 输出流式渲染（任务 1）
 *
 * 文件职责
 * --------
 * 本文件只管**状态机 + 三个流式请求**；
 * 各个步骤的界面在 `views/` 下，类型在 `types.ts`，词库拉取在 `wordbank.ts`。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import { outlinesApi } from "@/api/outlines";
import { charactersApi } from "@/api/characters";
import { readNdjsonStream, type StreamRequest } from "@/api/streams";
import type { GenreDef } from "@/config/genres";
import ChatInput from "@/components/ChatInput";
import type { CharProgress, NovelState, PlotVersion, Step } from "./types";
import { EMPTY_CHAR_PROGRESS } from "./types";
import WelcomeView from "./views/WelcomeView";
import SeedView from "./views/SeedView";
import PlotStreamView from "./views/PlotStreamView";
import OutlineStreamView from "./views/OutlineStreamView";
import CharacterStreamView from "./views/CharacterStreamView";
import DoneView from "./views/DoneView";

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
  const [charProgress, setCharProgress] = useState<CharProgress>(EMPTY_CHAR_PROGRESS);
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
    setCharProgress(EMPTY_CHAR_PROGRESS);
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
    setCharProgress(EMPTY_CHAR_PROGRESS);
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
      setCharProgress(EMPTY_CHAR_PROGRESS);
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
