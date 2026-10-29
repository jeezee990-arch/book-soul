/**
 * 请求序号守卫的单元测试（2026-10-29）。
 *
 * 对应 bug：种子库切换板块时，旧响应覆盖新数据
 * → Tab 显示板块 B、列表却是板块 A 的词，而写操作按 B 执行
 * → 用户看着 A 的列表误删 B 的词条。
 */

import { describe, expect, it } from "vitest";
import { createRequestGuard } from "../request-guard";

describe("createRequestGuard", () => {
  it("第一次领到的序号是当前序号", () => {
    const guard = createRequestGuard();
    const seq = guard.next();
    expect(guard.isCurrent(seq)).toBe(true);
  });

  it("序号严格递增", () => {
    const guard = createRequestGuard();
    const a = guard.next();
    const b = guard.next();
    expect(b).toBeGreaterThan(a);
  });

  it("领了新序号后，旧序号立即失效", () => {
    const guard = createRequestGuard();
    const first = guard.next();
    const second = guard.next();
    expect(guard.isCurrent(first)).toBe(false);
    expect(guard.isCurrent(second)).toBe(true);
  });

  it("乱序到达时只认最后一次请求（核心场景）", () => {
    const guard = createRequestGuard();
    // 用户先点 A，再点 B
    const seqA = guard.next();
    const seqB = guard.next();
    // B 的响应先到 → 采纳
    expect(guard.isCurrent(seqB)).toBe(true);
    // A 的响应后到 → 丢弃，不能覆盖 B
    expect(guard.isCurrent(seqA)).toBe(false);
  });

  it("连续切三个板块时只有最后那个有效", () => {
    const guard = createRequestGuard();
    const seqs = [guard.next(), guard.next(), guard.next()];
    expect(seqs.filter((s) => guard.isCurrent(s))).toEqual([seqs[2]]);
  });

  it("两个守卫实例互不影响", () => {
    const a = createRequestGuard();
    const b = createRequestGuard();
    const seqA = a.next();
    const seqB = b.next();
    expect(a.isCurrent(seqA)).toBe(true);
    expect(b.isCurrent(seqB)).toBe(true);
    expect(a.isCurrent(seqB)).toBe(false);
  });
});
