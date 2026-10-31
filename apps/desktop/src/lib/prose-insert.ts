/**
 * ProseMirror 流式插入（纯 model / state，**不碰 DOM**）。
 *
 * 背景（2026-10-30 用户实测）
 * --------------------------
 * AI 生成的章节正文「多出大量空余字符、没有分段分行」。根因在前端：
 * `NovelEditor.flushAppend` 原来在**文档末尾** `insertText`：
 *
 * ```js
 * const docSize = view.state.doc.content.size;   // ← 最后一个段落**之外**
 * const tr = view.state.tr.insertText(text, docSize);
 * ```
 *
 * ProseMirror 在段落之外插入会**新建一个段落** → 而流式是按 16ms 分批 flush
 * → 每批多一个段落 → Tiptap 的 `getText()` 用 `"\n\n"` 拼块 →
 * 用户库里那章 1012 个假段落、5338 个字符（真实正文只有 3314 字）。
 *
 * 修法
 * ----
 * 1. 追加要插到**最后一个段落内部**的末尾（`lastBlockEndPos`）
 * 2. 模型给的 `\n` / `\n\n` 要变成**真正的段落**（`insertWithParagraphBreaks`）
 *
 * 这个模块是纯函数（只吃 `Transaction`、返回新 `Transaction`），
 * 所以能在 node 环境直接单测（不需要 jsdom）。
 */

import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import type { Transaction } from "@tiptap/pm/state";

/**
 * 最后一个文本块（段落）**内部**的末尾位置。
 *
 * 位置算法：
 * ```
 * pos = doc.content.size - lastChild.nodeSize + 1 + lastChild.content.size
 * ```
 * 例：`<p>abc</p>` → `5 - 5 + 1 + 3 = 4`（正好是 "abc" 之后、段落内部）；
 * 空段落 `<p></p>` → `2 - 2 + 1 + 0 = 1`。
 *
 * @param doc 当前文档
 * @returns 可插入文本的位置
 */
export function lastBlockEndPos(doc: ProseMirrorNode): number {
  const last = doc.lastChild;
  if (!last) return 1;
  // 最后一个节点不是文本块（极少见的块级节点）→ 退回文档末尾
  if (!last.isTextblock) return doc.content.size;
  return doc.content.size - last.nodeSize + 1 + last.content.size;
}

/**
 * 在 `pos` 处插入带段落分隔的文本。
 *
 * - 文本里的换行（`\n` / `\n\n`）→ 在该处**断开段落**（`tr.split`）
 * - 连续换行只断一次（`\n\n` 是一个段落分隔，不是两个空段落）
 * - ⚠️ **以换行结尾的文本也必须断段** —— 后端排版器正是在段末输出 `\n\n`，
 *   而 flush 按 16ms 随机切批；批次恰好断在 `\n\n` 上而丢掉这个分隔，
 *   段落边界就会**随机丢失**（实测踩过："第一段。\n\n" + "第二段。"
 *   合并成了一个段落）。
 * - `split` 会改变后续位置 → 每插一段都**重新算位置**
 *
 * @param tr 事务（不可变，返回新事务）
 * @param pos 插入起点
 * @param text 待插入文本（可含换行）
 * @returns 新事务 + 插入结束位置
 */
export function insertWithParagraphBreaks(
  tr: Transaction,
  pos: number,
  text: string,
): { tr: Transaction; end: number } {
  // 按"内容 / 换行"交替切开（保留分隔符 —— 才能知道末尾有没有换行）
  const parts = text.split(/(\n+)/);
  let end = pos;
  let needBreak = false;

  /** 在 end 处断开段落；返回新的结束位置 */
  const breakHere = (): number => {
    const parent = tr.doc.resolve(end).parent;
    // 当前段落非空才 split —— 对空段落 split 会多出一个空段落
    if (!parent.isTextblock || parent.content.size === 0) return end;
    tr = tr.split(end);
    // split 之后重新算（比手工 +2 稳）
    return lastBlockEndPos(tr.doc);
  };

  for (const part of parts) {
    if (!part) continue;
    if (/^\n+$/.test(part)) {
      // 连续的换行只算一个断段
      needBreak = true;
      continue;
    }
    if (needBreak) {
      end = breakHere();
      needBreak = false;
    }
    // 用 replaceWith 而不是 insertText：insertText 会**继承光标处的标记**
    // （上一段是加粗 → 追加的正文跟着变粗），这里要的是纯文本。
    tr = tr.replaceWith(end, end, tr.doc.type.schema.text(part));
    end = lastBlockEndPos(tr.doc);
  }

  // 文本以换行结尾 → 立刻断段，下一批从新段落开始写
  if (needBreak) {
    end = breakHere();
  }

  return { tr, end };
}
