/**
 * 作品命名纯逻辑的单元测试（2026-10-30）。
 *
 * 背景：用户实测反馈"写新书程序自动命名的名字与素材库重复的时候
 * 无法保存到素材库中"。根因是后端按名字 upsert + 素材库允许重名。
 * 修复后：**同一时间只能有一本同名作品**，规则前后端一致：
 *
 * - 前端：``lib/novel-name.ts``（输入时立刻提示）
 * - 后端：``NovelService.name_taken`` / ``unique_name``（权威）
 *
 * 这里锁住前端的规则 —— 两边不一致的话，用户会看到
 * "前端说不冲突、后端说冲突"。
 */

import { describe, expect, it } from "vitest";
import { duplicateHint, isNameTaken, uniqueName } from "../novel-name";

describe("isNameTaken", () => {
  it("没占用返回 false", () => {
    expect(isNameTaken("剑起青云", ["别的书"])).toBe(false);
  });

  it("占用返回 true", () => {
    expect(isNameTaken("剑起青云", ["剑起青云"])).toBe(true);
  });

  it("忽略首尾空白（与后端 strip 一致）", () => {
    expect(isNameTaken("  剑起青云  ", ["剑起青云"])).toBe(true);
    expect(isNameTaken("剑起青云", ["  剑起青云  "])).toBe(true);
  });

  it("空名不算占用", () => {
    expect(isNameTaken("   ", ["剑起青云"])).toBe(false);
  });

  it("大小写不同算不同的书（与后端一致，后端不做大小写折叠）", () => {
    expect(isNameTaken("A Book", ["a book"])).toBe(false);
  });
});

describe("uniqueName", () => {
  it("没人用就原样返回", () => {
    expect(uniqueName("剑起青云", ["别的书"])).toBe("剑起青云");
  });

  it("被占用就加序号", () => {
    expect(uniqueName("修仙新作", ["修仙新作"])).toBe("修仙新作 2");
  });

  it("序号也占了就继续加", () => {
    expect(uniqueName("修仙新作", ["修仙新作", "修仙新作 2"])).toBe(
      "修仙新作 3",
    );
  });

  it("跳过序号空洞（后端也是从 2 顺序往上找）", () => {
    // 后端：base 被占 → "base 2"；"base 2" 被占 → "base 3"
    expect(uniqueName("修仙新作", ["修仙新作", "修仙新作 2"])).toBe("修仙新作 3");
  });

  it("名字带空白时先裁掉", () => {
    expect(uniqueName("  修仙新作  ", ["修仙新作"])).toBe("修仙新作 2");
  });

  it("空名原样返回", () => {
    expect(uniqueName("   ", ["修仙新作"])).toBe("");
  });
});

describe("duplicateHint", () => {
  it("不重名时返回 null", () => {
    expect(duplicateHint("剑起青云", ["别的书"])).toBeNull();
  });

  it("重名时给出改用哪个名字的提示", () => {
    const hint = duplicateHint("修仙新作", ["修仙新作"]);
    expect(hint).toContain("修仙新作");
    expect(hint).toContain("修仙新作 2");
  });

  it("改名时排除自己那本（不算冲突）", () => {
    expect(duplicateHint("修仙新作", ["修仙新作"], "修仙新作")).toBeNull();
  });

  it("排除是按**名字**排除的（同名只可能有一本，等价于排除自己）", () => {
    // 素材库里同名只有一本，所以"排除自己"和"排除同名"是一回事
    expect(duplicateHint("同名", ["同名", "同名"], "同名")).toBeNull();
  });

  it("排除自己之后，撞上别的书仍然提示", () => {
    const hint = duplicateHint("乙书", ["甲书", "乙书"], "甲书");
    expect(hint).not.toBeNull();
    expect(hint).toContain("乙书 2");
  });

  it("空名不提示", () => {
    expect(duplicateHint("  ", ["修仙新作"])).toBeNull();
  });
});
