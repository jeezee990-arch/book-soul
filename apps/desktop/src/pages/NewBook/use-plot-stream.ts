/**
 * 剧情生成流（步骤 1 → 2）。
 *
 * 独立成文件的原因
 * ----------------
 * `NewBook/index.tsx` 原本把三条流 + 计时 + 渲染全塞在一起，超过 500 行
 * （AGENTS.md §8.1）。三条流各自是一个独立职责，拆开后每条流单独可测。
 *
 * 流式契约（AGENTS.md §4.1）：走 NDJSON，逐行读。
 * ⚠️ §4.10：失败分 **transport**（HTTP 层）和 **server**（流内帧）两类，
 *    两者都要用 `detectStreamFailure` 认，否则界面永远转圈。
 */

import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { inspirationsApi } from "@/api/inspirations";
import {
  readNdjsonStream,
  detectStreamFailure,
  appendThinking,
  type StreamRequest,
} from "@/api/streams";
import { useNewBookStore } from "@/stores/newbook-store";
import type { ElapsedTimer } from "./use-elapsed-timer";
import { abortPlot, clearPlotAbort, setPlotAbort } from "./stream-abort";

/** 剧情流对外接口。 */
export interface PlotStreamApi {
  /** 生成 3 个剧情版本。 */
  startPlotStream: () => Promise<void>;
  /** 停止生成（用户主动中断）。 */
  stopPlotStream: () => void;
}

/**
 * 剧情生成流。
 *
 * @param timer 共享计时器（三条流共用一个）
 * @returns 流控制接口
 */
export function usePlotStream(timer: ElapsedTimer): PlotStreamApi {
  const { startElapsed, stopElapsed, elapsedValueRef } = timer;

  const genre = useNewBookStore((s) => s.genre);
  const keywords = useNewBookStore((s) => s.keywords);
  const ideas = useNewBookStore((s) => s.ideas);
  const setPlotVersions = useNewBookStore((s) => s.setPlotVersions);
  const setPlotStreaming = useNewBookStore((s) => s.setPlotStreaming);
  const setPlotThinking = useNewBookStore((s) => s.setPlotThinking);
  const setPlotErrors = useNewBookStore((s) => s.setPlotErrors);
  const setChosenPlotIdx = useNewBookStore((s) => s.setChosenPlotIdx);
  const setPlotBusy = useNewBookStore((s) => s.setPlotBusy);
  const setPlotStats = useNewBookStore((s) => s.setPlotStats);
  const setStep = useNewBookStore((s) => s.setStep);

  /** 发给后端的"作者个人想法"——把词条拼成多行文本。 */
  const userExtra = useMemo(() => ideas.join("\n"), [ideas]);

  /**
   * 停止剧情生成（用户主动中断）。
   *
   * ⚠️ 必须真的 `abort()` —— 只清 busy 标志的话后端还在烧 token，
   *    而且 `finally` 里还会再跑一遍 setPlotBusy(false)。
   */
  const stopPlotStream = useCallback(() => {
    abortPlot();
    setPlotBusy(false);
    stopElapsed();
  }, [setPlotBusy, stopElapsed]);

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
    setPlotAbort(ctrl);
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
          // ⚠️ 后端给**单个版本**的错误带上 index（2026-10-25）。
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
      clearPlotAbort(ctrl);
      setPlotBusy(false);
      stopElapsed();
    }
  }, [
    genre,
    keywords,
    userExtra,
    startElapsed,
    stopElapsed,
    elapsedValueRef,
    setPlotVersions,
    setPlotStreaming,
    setPlotThinking,
    setPlotErrors,
    setChosenPlotIdx,
    setPlotBusy,
    setPlotStats,
    setStep,
  ]);

  return { startPlotStream, stopPlotStream };
}
