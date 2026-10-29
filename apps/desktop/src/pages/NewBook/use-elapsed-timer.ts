/**
 * 生成耗时计时器（开新书向导三条流共用）。
 *
 * 为什么单独抽出来
 * ----------------
 * 剧情 / 大纲 / 人物卡三条流都要"开始计时 / 停止计时 / 拿兜底耗时"，
 * 抽成一个 hook 后三条流只依赖它，逻辑只有一份。
 *
 * ⚠️ 显示的秒数是**算出来的**（now - elapsedStartedAt），不是累加的 ——
 *    累加值在"切到别的页面再回来"时会停在切走的那一刻。
 *    起始时刻存在 store 里，所以切页回来能接着算。
 */

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { useNewBookStore } from "@/stores/newbook-store";

/** 计时器对外接口。 */
export interface ElapsedTimer {
  /** 已耗时秒数（渲染用）。 */
  elapsedSec: number;
  /**
   * 兜底耗时引用。
   *
   * 后端没返回 `elapsed_sec` 时用它兜底 —— 流式回调里要读到**当前**值，
   * 用 state 会因为闭包拿到旧值，所以用 ref。
   */
  elapsedValueRef: MutableRefObject<number>;
  /** 开始计时（重置为 0）。 */
  startElapsed: () => void;
  /** 停止计时。 */
  stopElapsed: () => void;
}

/**
 * 生成耗时计时器。
 *
 * @returns 计时器接口（秒数 / 兜底引用 / 开始 / 停止）
 */
export function useElapsedTimer(): ElapsedTimer {
  const elapsedStartedAt = useNewBookStore((s) => s.elapsedStartedAt);
  const setElapsedStartedAt = useNewBookStore((s) => s.setElapsedStartedAt);

  /**
   * 每秒 tick 一次，只为触发重渲染。
   */
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (elapsedStartedAt === null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [elapsedStartedAt]);

  const elapsedSec =
    elapsedStartedAt === null ? 0 : Math.floor((now - elapsedStartedAt) / 1000);
  const elapsedValueRef = useRef(0);

  // 把算出来的秒数同步到 ref —— 后端没给 elapsed_sec 时用它兜底。
  //
  // ⚠️ 2026-10-25 巡检：这个 ref 以前**永远是 0**（声明了但没人更新），
  // 于是「后端没返回耗时」时统计显示 0 秒。现在每次渲染同步一次。
  useEffect(() => {
    elapsedValueRef.current = elapsedSec;
  }, [elapsedSec]);

  const startElapsed = useCallback(() => {
    elapsedValueRef.current = 0;
    setElapsedStartedAt(Date.now());
  }, [setElapsedStartedAt]);

  const stopElapsed = useCallback(() => {
    setElapsedStartedAt(null);
  }, [setElapsedStartedAt]);

  return { elapsedSec, elapsedValueRef, startElapsed, stopElapsed };
}
