/**
 * ProseMirror 流式插入测试（2026-10-30）。
 *
 * 这层是**纯 model / state**（不碰 DOM），所以能在 node 环境直接测。
 *
 * 覆盖用户实测的重大事故：流式追加在文档末尾插入 → 每批新建一个段落
 * → Tiptap `getText()` 用 `"\n\n"` 拼块 → 正文被切成成百上千个假段落。
 */

import { Schema } from "@tiptap/pm/model";
import { EditorState } from "@tiptap/pm/state";
import { describe, expect, it } from "vitest";
import { insertWithParagraphBreaks, lastBlockEndPos } from "../prose-insert";

/** 最小 schema：doc > paragraph > text（和 Tiptap 的 StarterKit 一致的结构） */
const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { content: "text*", group: "block" },
    text: {},
  },
});

/** 建一个只有空段落的文档 */
function emptyState(): EditorState {
  return EditorState.create({
    doc: schema.node("doc", null, [schema.node("paragraph")]),
  });
}

/** 模拟一次 flush：按 16ms 批次把文本追加进文档 */
function appendBatches(
  state: EditorState,
  batches: string[],
): EditorState {
  let s = state;
  for (const batch of batches) {
    const pos = lastBlockEndPos(s.doc);
    const { tr } = insertWithParagraphBreaks(s.tr, pos, batch);
    s = s.apply(tr);
  }
  return s;
}

/** 取出 Tiptap getText() 等价的文本 */
function getText(state: EditorState): string {
  return state.doc.textBetween(0, state.doc.content.size, "\n\n");
}

describe("lastBlockEndPos", () => {
  it("指向最后一个段落内部的末尾", () => {
    const state = EditorState.create({
      doc: schema.node("doc", null, [
        schema.node("paragraph", null, [schema.text("abc")]),
      ]),
    });
    // <p>abc</p> → content.size=5, nodeSize=5, content.size=3 → 4
    expect(lastBlockEndPos(state.doc)).toBe(4);
  });

  it("空段落指向段落内部", () => {
    expect(lastBlockEndPos(emptyState().doc)).toBe(1);
  });
});

describe("insertWithParagraphBreaks", () => {
  it("多次追加不会再新建段落（回归：用户库 1012 个假段落）", () => {
    const state = appendBatches(emptyState(), ["山", "门", "前", "的", "铜", "钟"]);
    // 只有初始那一个段落
    expect(state.doc.childCount).toBe(1);
    expect(getText(state)).toBe("山门前的铜钟");
  });

  it("换行会断开成真正的段落", () => {
    const state = appendBatches(emptyState(), ["第一段。\n\n第二段。"]);
    expect(state.doc.childCount).toBe(2);
    expect(getText(state)).toBe("第一段。\n\n第二段。");
  });

  it("单个换行也断段", () => {
    const state = appendBatches(emptyState(), ["甲\n乙"]);
    expect(state.doc.childCount).toBe(2);
  });

  it("连续换行只断一次（不产生空段落）", () => {
    const state = appendBatches(emptyState(), ["甲\n\n\n\n乙"]);
    expect(state.doc.childCount).toBe(2);
    expect(getText(state)).toBe("甲\n\n乙");
  });

  it("跨批次追加：段落边界不丢", () => {
    // 第一批结尾有换行，第二批接着写
    const state = appendBatches(emptyState(), ["第一段。\n\n", "第二段。"]);
    expect(state.doc.childCount).toBe(2);
    expect(getText(state)).toBe("第一段。\n\n第二段。");
  });

  it("插入的是纯文本（不继承光标标记）", () => {
    const state = appendBatches(emptyState(), ["普通"]);
    expect(getText(state)).toBe("普通");
    expect(state.doc.firstChild?.childCount).toBe(1);
  });
});
