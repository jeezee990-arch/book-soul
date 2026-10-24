/**
 * 流式内容区的「自动跟随最新内容」规则。
 *
 * 剧情卡（plot-step）和大纲原文区（outline-step）都需要这个行为 ——
 * 之前是两份复制粘贴的 useEffect，改一处漏一处就会出现「流式不跟随」的回归。
 * 抽到这里，顺便让它可单测（纯函数，不依赖 DOM 环境）。
 */

/** 判定「用户本来就在底部附近」的阈值（px）。 */
export const AUTO_SCROLL_THRESHOLD_PX = 48;

/** 滚动容器需要暴露的最小接口（DOM 的 HTMLElement 天然满足）。 */
export interface ScrollTarget {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
}

/**
 * 距离底部的距离（px），不会为负。
 *
 * 真实 DOM 里 `scrollHeight >= clientHeight` 恒成立；这里再钳一次，
 * 是为了内容短于视口时也返回 0（而不是负数）—— 语义更明确，测试也更稳定。
 */
export function distanceToBottom(el: ScrollTarget): number {
  return Math.max(0, el.scrollHeight - el.scrollTop - el.clientHeight);
}

/**
 * 用户是否「本来就在底部附近」。
 *
 * 只有这时候才自动滚到底 —— 否则用户想回头看前面写的字，
 * 会被强行拽回底部（很烦）。
 */
export function isNearBottom(
  el: ScrollTarget,
  threshold: number = AUTO_SCROLL_THRESHOLD_PX,
): boolean {
  return distanceToBottom(el) < threshold;
}

/** 滚到底部。 */
export function scrollToBottom(el: ScrollTarget): void {
  el.scrollTop = el.scrollHeight;
}
