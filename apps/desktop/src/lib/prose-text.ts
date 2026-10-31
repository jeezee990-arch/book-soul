/**
 * 正文纯文本处理：段落切分 + 真实字数 + 转成编辑器 HTML。
 *
 * ⚠️ **口径必须与后端一致**（`server/src/core/prose_format.py`）：
 * - 段落分隔：空行（`\n\n`）；单个 `\n` 也当段落分隔；空段丢弃
 * - 字数：**非空白字符数**（汉字 / 中文标点 / 英文 / 数字都算，
 *   空格 / 制表符 / 换行符都不算）—— 与 Word 的「字数」统计一致，
 *   也是起点 / 番茄等网文平台的通行口径
 *
 * ⚠️ 为什么不能直接用 `text.length` 当字数：
 * `len` 把换行符、空格全算进去 → 界面显示的字数虚高，和 Word 统计对不上
 * （用户实测 5338 vs 3309 —— 差额全是段落分隔符）。
 *
 * 这个文件是**纯逻辑**（不碰 DOM / ProseMirror），所以能直接单测。
 */

/** 段落分隔（与后端 `re.split(r"\n\s*\n|\n", ...)` 等价）。 */
const PARAGRAPH_BREAK_RE = /\n\s*\n|\n/;

/**
 * 空白字符。
 *
 * JS 的 `\s` 本身已经包含全角空格 U+3000，这里再显式写一遍，
 * 是为了让"全角空格不算字数"这条口径在代码里一眼可见。
 */
const WHITESPACE_RE = /[\s\u3000]/;

/**
 * 把纯文本按段落切开。
 *
 * - 空行（`\n\n`）是段落分隔；单个 `\n` 也当分隔（模型有时只给一个换行）
 * - 空段丢弃；每段去掉首尾空白
 *
 * @param text 纯文本
 * @returns 段落列表（每段已去首尾空白，无空段）
 */
export function splitParagraphs(text: string): string[] {
  if (!text) return [];
  const normalized = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  return normalized
    .split(PARAGRAPH_BREAK_RE)
    .map((p) => p.trim())
    .filter((p) => p.length > 0);
}

/**
 * 真实字数：**非空白字符数**。
 *
 * 汉字、中文标点、英文单词、数字都算；空格、制表符、换行符都不算。
 * 与后端 `count_prose_words` 完全一致。
 *
 * @param text 纯文本
 * @returns 字数
 */
export function countProseWords(text: string): number {
  if (!text) return 0;
  let n = 0;
  // 用 for...of 按**码点**迭代（与 Python 的 `for c in text` 一致）：
  // 一个 emoji 算 1 个字，不是 2 个。
  for (const ch of text) {
    if (!WHITESPACE_RE.test(ch)) n += 1;
  }
  return n;
}

/**
 * HTML 转义。
 *
 * ⚠️ 正文里出现 `<` `>` `&` 必须转义 —— 否则会被当成标签解析，
 * 用户写的 `<他在笑>` 会被吃掉一半。
 *
 * @param text 原始文本
 * @returns 转义后的文本
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * 纯文本 → 段落化 HTML（每段一个 `<p>`）。
 *
 * ⚠️ 为什么不能把纯文本直接丢给 `setContent`：
 * Tiptap 按 **HTML** 解析 → 整章纯文本变成**一个段落**，
 * 段内的 `\n` 变成字面字符 → HTML 渲染时 `\n` 折叠成空格 →
 * 界面上就是"一行行挤在一起、字间有空格"。
 *
 * @param text 纯文本（`\n\n` 分段）
 * @returns 段落化 HTML（无段落时返回空串）
 */
export function plainTextToParagraphHtml(text: string): string {
  const paragraphs = splitParagraphs(text);
  if (paragraphs.length === 0) return "";
  return paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("");
}
