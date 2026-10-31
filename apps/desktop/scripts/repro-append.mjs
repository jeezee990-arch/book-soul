/**
 * 复现 NovelEditor.flushAppend 的插入行为（纯 prosemirror，不需要 DOM）。
 *
 * 怀疑点：flushAppend 用 `tr.insertText(text, doc.content.size)` 在文末插入，
 * 而 Tiptap 的 getText() 默认 blockSeparator="\n\n" ——
 * 如果每次插入都新建一个段落，getText() 就会在每段之间插 "\n\n"。
 */

import { Schema } from "@tiptap/pm/model";
import { EditorState } from "@tiptap/pm/state";

const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { content: "text*", group: "block" },
    text: {},
  },
});

// 模拟一个空章节：<p></p>
let state = EditorState.create({ doc: schema.node("doc", null, [schema.node("paragraph")]) });

// 模拟 LLM 的流式 delta：一小段一小段吐字
const chunks = ["山", "门前的", "铜", "钟连", "响三", "声，雾便从青石", "阶", "下退了", "。"];

for (const chunk of chunks) {
  const docSize = state.doc.content.size;
  const tr = state.tr.insertText(chunk, docSize);
  state = state.apply(tr);
}

console.log("=== 文档结构 ===");
console.log(JSON.stringify(state.doc.toJSON(), null, 2));

console.log("=== doc.content.size ===");
console.log(state.doc.content.size);

console.log("=== textBetween(blockSeparator='\\n\\n') —— Tiptap getText() 等价 ===");
console.log(JSON.stringify(state.doc.textBetween(0, state.doc.content.size, "\n\n")));

console.log("=== textBetween(blockSeparator='\\n') ===");
console.log(JSON.stringify(state.doc.textBetween(0, state.doc.content.size, "\n")));

console.log("=== 段落节点数 ===");
console.log(state.doc.childCount);

console.log("=== 换行符个数（\\n\\n）===");
const t = state.doc.textBetween(0, state.doc.content.size, "\n\n");
console.log((t.match(/\n\n/g) ?? []).length);
