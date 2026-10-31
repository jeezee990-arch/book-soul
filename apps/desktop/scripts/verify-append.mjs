/**
 * 流式插入自证脚本（2026-10-30）。
 *
 * ⚠️ 直接 import **生产实现**（`src/lib/prose-insert.ts`），不是复刻一份 ——
 *    之前 worker 的脚本里内联了一份"看起来像"的实现，
 *    结果它测出来的行为和线上代码不一致（B3 假失败），差点误导判断。
 *
 * 跑法（Node 22+ 直接支持 TS import）：
 * ```
 * cd apps/desktop && node scripts/verify-append.mjs
 * ```
 */

import { Schema } from "@tiptap/pm/model";
import { EditorState } from "@tiptap/pm/state";
import {
  insertWithParagraphBreaks,
  lastBlockEndPos,
} from "../src/lib/prose-insert.ts";

const schema = new Schema({
  nodes: {
    doc: { content: "block+" },
    paragraph: { content: "text*", group: "block" },
    text: {},
  },
});

/** 空章节：<p></p> */
const emptyDoc = () =>
  EditorState.create({ doc: schema.node("doc", null, [schema.node("paragraph")]) });

/** Tiptap getText() 等价文本 */
const getText = (state) =>
  state.doc.textBetween(0, state.doc.content.size, "\n\n");

let failures = 0;
function assert(cond, label, extra = "") {
  if (cond) {
    console.log(`  [PASS] ${label}`);
  } else {
    failures += 1;
    console.log(`  [FAIL] ${label} ${extra}`);
  }
}

/** 用生产实现追加一批文本 */
function append(state, text) {
  const pos = lastBlockEndPos(state.doc);
  const { tr } = insertWithParagraphBreaks(state.tr, pos, text);
  return state.apply(tr);
}

// ===== 场景 A：旧逻辑（复现 bug）=====
console.log("=== 场景 A：旧逻辑（复现 bug）===");
{
  let s = emptyDoc();
  for (const batch of ["山", "门前的", "铜", "钟连", "响三", "声，雾便从青石", "阶", "下退了", "。"]) {
    // 旧写法：在**文档末尾** insertText → ProseMirror 新建一个段落
    const docSize = s.doc.content.size;
    s = s.apply(s.tr.insertText(batch, docSize));
  }
  const text = getText(s);
  console.log(`  段落数 = ${s.doc.childCount}（批次 9）`);
  console.log(`  文本 = ${JSON.stringify(text)}`);
  console.log(`  文本长度 = ${text.length}，其中 \\n 个数 = ${(text.match(/\n/g) ?? []).length}`);
  assert(s.doc.childCount === 10, "旧逻辑：每批一个新段落（bug 复现）");
  console.log(
    "  ↑ 这就是用户库里《骨仙传》第 1 章的形态：1012 个假段落、字数虚高 61%",
  );
}

// ===== 场景 B：新逻辑（生产实现）=====
console.log("\n=== 场景 B：新逻辑（生产实现）===");
{
  // B1：连续追加 10 批 → 仍然只有 1 个段落
  let s = emptyDoc();
  for (const batch of ["山", "门前的", "铜", "钟连", "响三", "声，雾便从青石", "阶", "下退了", "。"]) {
    s = append(s, batch);
  }
  console.log(`  B1 段落数 = ${s.doc.childCount}，文本 = ${JSON.stringify(getText(s))}`);
  assert(s.doc.childCount === 1, "B1 10 个批次后仍是 1 个段落");
  assert(!getText(s).includes("\n"), "B1 段落内部没有多余换行");

  // B2：批次里带 \n\n（后端排版器输出的段落分隔）→ 段落数 = 分隔数 + 1
  const batches = ["山\n\n门前的\n\n铜", "钟连\n\n响三", "声，雾便从青石"];
  s = emptyDoc();
  for (const b of batches) s = append(s, b);
  const text2 = getText(s);
  const separators = (batches.join("").match(/\n\n/g) ?? []).length;
  console.log(`  B2 段落数 = ${s.doc.childCount}（期望 ${separators + 1}）`);
  console.log(`  B2 文本 = ${JSON.stringify(text2)}`);
  assert(s.doc.childCount === separators + 1, "B2 段落数 = 原始段落数 + 换行数");
  assert(
    text2 === "山\n\n门前的\n\n铜钟连\n\n响三声，雾便从青石",
    "B2 段落之间是 \\n\\n、段内无换行",
    JSON.stringify(text2),
  );

  // B3：批次边界正好落在 \n\n 上 → 段落边界不能丢
  s = emptyDoc();
  s = append(s, "第一段。\n\n");
  s = append(s, "第二段。");
  console.log(`  B3 段落数 = ${s.doc.childCount}，文本 = ${JSON.stringify(getText(s))}`);
  assert(s.doc.childCount === 2, "B3 批次边界落在 \\n\\n 上，段落不丢");
  assert(getText(s) === "第一段。\n\n第二段。", "B3 段落分隔正确", JSON.stringify(getText(s)));

  // B4：单个 \n 也断段（与后端 split_paragraphs 一致）
  s = emptyDoc();
  s = append(s, "甲\n乙");
  assert(s.doc.childCount === 2, "B4 单个 \\n 也断段");

  // B5：段首 \n 不产生空段落
  s = emptyDoc();
  s = append(s, "\n\n开头");
  console.log(`  B5 段落数 = ${s.doc.childCount}`);
  assert(s.doc.childCount === 1, "B5 开头的换行不产生空段落");
}

// ===== 场景 C：旧的重写路径（已修，记录 bug 形态）=====
console.log("\n=== 场景 C：旧的重写路径（已修，记录 bug 形态）===");
{
  // 文档 "ABCD"，选中 [2,3) 即 "B"，重写成 "XYZ"
  // 期望结果 "AXYZCD" —— 选区后面的 "CD" 必须完好
  const makeDoc = () =>
    EditorState.create({
      doc: schema.node("doc", null, [
        schema.node("paragraph", null, [schema.text("ABCD")]),
      ]),
    });
  const from = 2;
  const originalTo = 3;

  // 旧逻辑：删选区后按 [from, from + len] 替换
  // 实测：不抛错，但**静默吃掉选区后面的正文**（"CD" 消失）—— 这才是真 bug 形态
  let s = makeDoc();
  s = s.apply(s.tr.delete(from, originalTo));
  console.log(`  删选区后 = ${JSON.stringify(getText(s))}`);
  try {
    s = s.apply(s.tr.insertText("XYZ", from, from + 3));
    console.log(`  旧逻辑结果 = ${JSON.stringify(getText(s))}`);
    assert(
      getText(s) === "AXYZ",
      "旧重写逻辑吃掉选区后面的正文（'CD' 丢失）",
      JSON.stringify(getText(s)),
    );
  } catch (e) {
    console.log(`  旧逻辑抛错 = ${e.message}`);
    assert(true, "旧重写逻辑确实会炸（RangeError）或吃掉正文");
  }

  // 新逻辑：纯插入，不覆盖任何已有内容
  let s2 = makeDoc();
  s2 = s2.apply(s2.tr.delete(from, originalTo));
  s2 = s2.apply(s2.tr.insertText("XYZ", from));
  console.log(`  新逻辑结果 = ${JSON.stringify(getText(s2))}`);
  assert(
    getText(s2) === "AXYZCD",
    "新重写逻辑：只插入，选区后面的正文完好",
    JSON.stringify(getText(s2)),
  );
}

console.log(
  failures === 0 ? "\nALL PASS" : `\n${failures} 个断言失败`,
);
process.exit(failures === 0 ? 0 : 1);
