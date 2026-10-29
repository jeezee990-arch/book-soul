/**
 * 重命名载荷判定的单元测试（2026-10-29 评审修复）。
 *
 * 背景：重命名弹窗的「取消」/ ESC / 点遮罩以前都回传空串，
 * 等于"保存空标题" → 用户自定义标题被静默清空（点取消反而丢数据）。
 * 现在取消回传 null，必须判定为「不发请求」。
 */

import { describe, expect, it } from "vitest";
import { resolveRenamePayload } from "../inspiration-manage";

describe("resolveRenamePayload", () => {
  it("取消（null）返回 null —— 不发任何请求", () => {
    expect(resolveRenamePayload(null)).toBeNull();
  });

  it("空串表示清空标题（回落到自动摘要）", () => {
    expect(resolveRenamePayload("")).toEqual({ title: null });
  });

  it("只有空白也算清空", () => {
    expect(resolveRenamePayload("   ")).toEqual({ title: null });
  });

  it("正常标题原样提交", () => {
    expect(resolveRenamePayload("剑与霜")).toEqual({ title: "剑与霜" });
  });

  it("标题两端空白会被裁掉", () => {
    expect(resolveRenamePayload("  剑与霜  ")).toEqual({ title: "剑与霜" });
  });

  it("取消与清空是**两种不同的语义**", () => {
    // 这正是原 bug 的核心：以前两者被混成了同一个空串
    expect(resolveRenamePayload(null)).not.toEqual(resolveRenamePayload(""));
  });
});
