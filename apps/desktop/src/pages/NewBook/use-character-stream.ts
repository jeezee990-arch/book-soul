/**
 * 人物卡生成流（步骤 3）。
 *
 * 后端流程：先抽取人物名单 → 逐张并行生成卡片 → 落库。
 * ⚠️ AGENTS.md §4.8：LLM 调用并行，**写库串行**（后端已保证）。
 */

import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { charactersApi } from "@/api/characters";
import {
  readNdjsonStream,
  detectStreamFailure,
  appendThinking,
  type StreamRequest,
} from "@/api/streams";
import { useNewBookStore } from "@/stores/newbook-store";
import { EMPTY_CHAR_PROGRESS } from "./types";
import type { ElapsedTimer } from "./use-elapsed-timer";
import { abortChar, clearCharAbort, setCharAbort } from "./stream-abort";

/** 人物卡流对外接口。 */
export interface CharacterStreamApi {
  /**
   * 从大纲生成人物卡。
   *
   * @param novelId 作品 id
   * @param outline 大纲结构（后端据此抽取人物）
   */
  startCharacterStream: (
    novelId: number,
    outline: Record<string, unknown>,
  ) => Promise<void>;
}

/**
 * 人物卡生成流。
 *
 * @param timer 共享计时器
 * @returns 流控制接口
 */
export function useCharacterStream(
  timer: ElapsedTimer,
): CharacterStreamApi {
  const { startElapsed, elapsedValueRef } = timer;

  const genre = useNewBookStore((s) => s.genre);
  const ideas = useNewBookStore((s) => s.ideas);
  const setCharProgress = useNewBookStore((s) => s.setCharProgress);
  const setCharThinking = useNewBookStore((s) => s.setCharThinking);
  const setCharStats = useNewBookStore((s) => s.setCharStats);
  const setOutlinePhase = useNewBookStore((s) => s.setOutlinePhase);
  const setStep = useNewBookStore((s) => s.setStep);

  /** 发给后端的"作者个人想法"。 */
  const userExtra = useMemo(() => ideas.join("\n"), [ideas]);

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
      setCharAbort(ctrl);
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
              elapsedSec:
                (obj.elapsed_sec as number | undefined) ?? elapsedValueRef.current,
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
      } finally {
        clearCharAbort(ctrl);
      }
    },
    [
      genre,
      userExtra,
      startElapsed,
      elapsedValueRef,
      setCharProgress,
      setCharThinking,
      setCharStats,
      setOutlinePhase,
      setStep,
    ],
  );

  return { startCharacterStream };
}

/** 中断人物卡生成（外部用，比如"退回剧情页"）。 */
export function stopCharacterStream(): void {
  abortChar();
}
