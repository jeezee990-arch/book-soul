/**
 * 章节生成 / 重写的流式逻辑（从旧创作页迁出）。
 *
 * 为什么抽成 hook：生成与重写现在由右栏面板的按钮触发，
 * 但流式文本要同时写进编辑器 + 显示在右栏的状态卡里。
 * 放在 hook 里，index.tsx（持有编辑器 ref）与面板 Tab 都能消费同一份状态。
 *
 * 流式契约（AGENTS.md §4.1）：必须用 client.stream()，
 * 后端 /chapters/{id}/generate|rewrite 走 NDJSON，这里逐行读。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  readNdjsonStream,
  isStreamDone,
  isStreamThinking,
  detectStreamFailure,
  type StreamEvent,
} from "@/api/streams";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Chapter, ChapterVersion } from "@/lib/types";
import type { NovelEditorHandle } from "@/components/NovelEditor";

export interface ChapterSelection {
  from: number;
  to: number;
  text: string;
}

/**
 * 章节流事件分类结果。
 *
 * - ``fail``：流失败了（transport / server 两类都归到这里）
 * - ``done``：整流结束
 * - ``thinking``：推理模型在思考（**不进正文**，单独显示）
 * - ``text``：正文增量（进正文）
 * - ``ignore``：不认识的帧
 */
export type ChapterStreamAction =
  | { kind: "fail"; message: string }
  | { kind: "done" }
  | { kind: "thinking"; text: string }
  | { kind: "text"; text: string }
  | { kind: "ignore" };

/**
 * 把一个 ndjson 事件分类成"该干什么"。
 *
 * 抽成纯函数是为了能单测 —— hook 本身要 DOM 环境，这个项目没装
 * @testing-library/react（不为了测试引入新依赖）。
 *
 * ⚠️ 两类失败必须都认（AGENTS.md §4.10）：
 * - transport：``{"error": "422 ..."}``（HTTP 非 2xx）
 * - server：``{"event": "error", "message": "..."}``（流内错误帧）
 * 漏掉任何一类 → 界面永远转圈。
 *
 * ⚠️ 思考内容**不能丢**（§4.7）：推理模型先思考好几秒再写正文，
 * 丢掉思考 → 前端一个字都收不到 → 用户看到"生成卡住不动"。
 */
export function classifyChapterStreamEvent(ev: StreamEvent): ChapterStreamAction {
  const failure = detectStreamFailure(ev);
  if (failure) return { kind: "fail", message: failure.message };
  if (isStreamDone(ev)) return { kind: "done" };
  if (isStreamThinking(ev)) return { kind: "thinking", text: ev.text };
  if ("text" in ev && typeof ev.text === "string") return { kind: "text", text: ev.text };
  return { kind: "ignore" };
}

/**
 * 决定落库正文内容。
 *
 * 生成是**追加**、重写是**替换选区** —— 流式累积量（accumulated）
 * 都不是完整正文，直接存它会丢掉章节原有内容。
 * 所以优先用编辑器里的完整全文，取不到才退回累积量。
 */
export function pickSavedContent(
  fullText: string | undefined | null,
  fallback: string,
): string {
  const full = (fullText ?? "").trim();
  return full.length > 0 ? full : fallback;
}

export interface ChapterStreamApi {
  /** 正在生成正文 */
  generating: boolean;
  /** 正在重写选区 */
  rewriting: boolean;
  /** 本次流式产出的文本（右栏状态卡实时显示） */
  streamText: string;
  /**
   * 模型思考中的文本（推理模型的 ``<think>`` 段）。
   *
   * ⚠️ 思考内容**不能丢**（AGENTS.md §4.7）：推理模型先思考好几秒再写正文，
   * 丢掉思考 → 前端一个字都收不到 → 用户看到"生成卡住不动"。
   * 这里单独显示成"模型思考中…"，正文区保持不动。
   */
  thinkingText: string;
  /** 已耗时（秒） */
  elapsed: number;
  /** 当前模式（用于右栏展示） */
  mode: "generate" | "rewrite" | null;
  /** 流式生成正文 */
  startGenerate: (userPrompt: string, targetWordCount: number) => Promise<void>;
  /** 选区重写（必须传入当前选区） */
  startRewrite: (userPrompt: string, selection: ChapterSelection | null) => Promise<void>;
  /** 停止 */
  stop: () => void;
  /** 清空状态 */
  reset: () => void;
}

interface Params {
  /** 当前章节 */
  chapter: Chapter | null;
  /** 编辑器 ref（写回正文用） */
  editorRef: React.RefObject<NovelEditorHandle>;
  /** 保存成功后回调（更新章节字数 / 版本号） */
  onSaved: (version: ChapterVersion) => void;
}

export function useChapterStream({
  chapter,
  editorRef,
  onSaved,
}: Params): ChapterStreamApi {
  const [generating, setGenerating] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [thinkingText, setThinkingText] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);

  /** 计时器：流式开始时启动，结束时停 */
  const startTimer = useCallback(() => {
    setElapsed(0);
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setElapsed((e) => e + 1);
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const reset = useCallback(() => {
    setStreamText("");
    setThinkingText("");
    setElapsed(0);
  }, []);

  /** 写一条新版本（生成 / 重写结束后统一调用） */
  const persist = useCallback(
    async (
      content: string,
      trigger: string,
      prompt: string,
      metadata?: Record<string, unknown>,
    ) => {
      if (!chapter) return;
      try {
        const version = await chaptersApi.saveContent(chapter.id, {
          content,
          trigger,
          prompt: prompt || undefined,
          metadata,
        });
        onSaved(version);
      } catch (e: unknown) {
        const msg = e instanceof ApiError ? e.message : String(e);
        toast.error("保存版本失败", { description: msg });
      }
    },
    [chapter, onSaved],
  );

  /**
   * 取"当前编辑器的完整正文"作为落库内容。
   *
   * 为什么不能直接存流式累积的 accumulated：
   * - 生成是**追加**到章节末尾，accumulated 只有新增那部分 → 存它会丢掉原有正文
   * - 重写是**替换选区**，accumulated 只有新写的段落 → 存它会丢掉其余正文
   * 流式结束后编辑器里已经是最终形态，直接取它的全文才是对的。
   */
  const readFullText = useCallback(
    (fallback: string): string =>
      pickSavedContent(editorRef.current?.getText(), fallback),
    [editorRef],
  );

  /** 流式生成整章正文（追加到编辑器末尾） */
  const startGenerate = useCallback(
    async (userPrompt: string, targetWordCount: number) => {
      if (!chapter) return;
      if (generating || rewriting) return;

      setGenerating(true);
      setStreamText("");
      setThinkingText("");
      startTimer();
      abortRef.current = new AbortController();

      let accumulated = "";
      // ⚠️ 2026-10-25 巡检：流失败后如果还往下走，会把**半截正文**存成正式版本，
      //    而且用户会先看到红色「生成失败」再看到绿色「生成完成」——自相矛盾。
      //    这里用 failed 标记：失败就**不落库**、不再报成功。
      let failed = false;
      try {
        for await (const ev of readNdjsonStream(
          `/chapters/${chapter.id}/generate`,
          {
            method: "POST",
            body: {
              user_prompt: userPrompt || "",
              target_word_count: targetWordCount,
            },
            signal: abortRef.current.signal,
          },
        )) {
          // ⚠️ 两类失败都要认（AGENTS.md §4.10）：transport（非 2xx）
          //    与 server（流内 error 帧）——漏掉任何一类界面都会永远转圈。
          const action = classifyChapterStreamEvent(ev);
          if (action.kind === "fail") {
            failed = true;
            toast.error("生成失败", { description: action.message });
            break;
          }
          if (action.kind === "done") break;
          if (action.kind === "thinking") {
            // 思考内容单独显示，**不进正文**（正文里混进英文思考是灾难）
            setThinkingText((t) => t + action.text);
            continue;
          }
          if (action.kind !== "text") continue;
          accumulated += action.text;
          setStreamText(accumulated);
          editorRef.current?.appendText(action.text);
        }
        // 流式完成：立即 flush 缓冲区
        editorRef.current?.flush();
        if (failed) {
          // 半截正文留在编辑器里（用户可以自己接着改），但**不落库**
          return;
        }
        const finalText = accumulated.trim();
        if (finalText) {
          // 存的是编辑器的完整正文（原有正文 + 本次新增）
          const full = readFullText(finalText);
          await persist(full, "llm_generate", userPrompt);
          toast.success("生成完成", { description: `本章共 ${full.length} 字` });
        } else {
          toast.warning("生成未产生内容");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!msg.includes("abort") && msg !== "The user aborted a request.") {
          toast.error("生成异常", { description: msg });
        }
      } finally {
        setGenerating(false);
        stopTimer();
        abortRef.current = null;
      }
    },
    [
      chapter,
      generating,
      rewriting,
      startTimer,
      stopTimer,
      persist,
      readFullText,
      editorRef,
    ],
  );

  /** 选区重写（把选中段落替换掉） */
  const startRewrite = useCallback(
    async (userPrompt: string, selection: ChapterSelection | null) => {
      if (!chapter) {
        toast.error("请先选择章节");
        return;
      }
      if (generating || rewriting) return;
      if (!selection) {
        toast.error("请先在编辑器中选中文本");
        return;
      }

      setRewriting(true);
      setStreamText("");
      setThinkingText("");
      startTimer();
      abortRef.current = new AbortController();

      const { from, to, text: originalText } = selection;
      let accumulated = "";
      // 同生成路径：失败就不落库、不再报成功（2026-10-25 巡检）
      let failed = false;
      try {
        for await (const ev of readNdjsonStream(
          `/chapters/${chapter.id}/rewrite`,
          {
            method: "POST",
            body: {
              original_text: originalText,
              user_prompt: userPrompt,
              from_pos: from,
              to_pos: to,
            },
            signal: abortRef.current.signal,
          },
        )) {
          const action = classifyChapterStreamEvent(ev);
          if (action.kind === "fail") {
            failed = true;
            toast.error("重写失败", { description: action.message });
            break;
          }
          if (action.kind === "done") break;
          if (action.kind === "thinking") {
            setThinkingText((t) => t + action.text);
            continue;
          }
          if (action.kind !== "text") continue;
          accumulated += action.text;
          setStreamText(accumulated);
          // 用增量替换：只传新增 chunk，编辑器内部累加并替换选区
          editorRef.current?.replaceSelection(from, to, action.text);
        }
        editorRef.current?.flush();
        if (failed) {
          // 半截重写留在编辑器里（用户可自行调整），但**不落库**
          return;
        }
        const finalText = accumulated.trim();
        if (finalText) {
          // 存的是编辑器的完整正文（选区已被新内容替换）
          const full = readFullText(finalText);
          await persist(full, "rewrite", userPrompt, {
            from,
            to,
            original_length: originalText.length,
          });
          toast.success("重写完成", {
            description: `替换 ${originalText.length} → ${finalText.length} 字`,
          });
        } else {
          toast.warning("重写未产生内容");
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!msg.includes("abort") && msg !== "The user aborted a request.") {
          toast.error("重写异常", { description: msg });
        }
      } finally {
        setRewriting(false);
        stopTimer();
        abortRef.current = null;
      }
    },
    [
      chapter,
      generating,
      rewriting,
      startTimer,
      stopTimer,
      persist,
      readFullText,
      editorRef,
    ],
  );

  // 卸载：中止请求 + 清计时器
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, []);

  return {
    generating,
    rewriting,
    streamText,
    thinkingText,
    elapsed,
    mode: generating ? "generate" : rewriting ? "rewrite" : null,
    startGenerate,
    startRewrite,
    stop,
    reset,
  };
}
