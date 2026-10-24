/**
 * 自动跟随滚动规则的单元测试。
 *
 * 这是「流式时能看到正在写的字」这个体验的护栏 ——
 * 之前 plot-step / outline-step 各写一份 useEffect，改坏一处不会报错，
 * 只会变成「流式看起来卡住了」。
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_SCROLL_THRESHOLD_PX,
  distanceToBottom,
  isNearBottom,
  scrollToBottom,
  type ScrollTarget,
} from "../auto-scroll";

/** 造一个可滚动的假容器。 */
function makeEl(scrollHeight: number, scrollTop: number, clientHeight: number): ScrollTarget {
  return { scrollHeight, scrollTop, clientHeight };
}

describe("distanceToBottom", () => {
  it("内容没溢出时为 0", () => {
    expect(distanceToBottom(makeEl(100, 0, 200))).toBe(0);
  });

  it("滚到最底时为 0", () => {
    expect(distanceToBottom(makeEl(1000, 800, 200))).toBe(0);
  });

  it("在中间时等于剩余距离", () => {
    expect(distanceToBottom(makeEl(1000, 300, 200))).toBe(500);
  });
});

describe("isNearBottom", () => {
  it("底部附近 → true（应该自动跟随）", () => {
    expect(isNearBottom(makeEl(1000, 800, 200))).toBe(true);
  });

  it("距离底部恰好在阈值内 → true", () => {
    const el = makeEl(1000, 800 - (AUTO_SCROLL_THRESHOLD_PX - 1), 200);
    expect(isNearBottom(el)).toBe(true);
  });

  it("距离底部超过阈值 → false（用户回头在看，不能拽回去）", () => {
    const el = makeEl(1000, 800 - (AUTO_SCROLL_THRESHOLD_PX + 1), 200);
    expect(isNearBottom(el)).toBe(false);
  });

  it("用户滚到顶 → false", () => {
    expect(isNearBottom(makeEl(1000, 0, 200))).toBe(false);
  });

  it("内容不足一屏 → true（没有可滚的部分，跟着无所谓）", () => {
    expect(isNearBottom(makeEl(80, 0, 200))).toBe(true);
  });
});

describe("scrollToBottom", () => {
  it("把 scrollTop 设为 scrollHeight", () => {
    const el = makeEl(1000, 0, 200);
    scrollToBottom(el);
    expect(el.scrollTop).toBe(1000);
  });
});
