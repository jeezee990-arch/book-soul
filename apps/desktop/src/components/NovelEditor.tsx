import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Selection } from "@tiptap/extensions";
import { Placeholder } from "@tiptap/extensions/placeholder";
import { plainTextToParagraphHtml } from "@/lib/prose-text";
import {
  insertWithParagraphBreaks,
  lastBlockEndPos,
} from "@/lib/prose-insert";

export interface NovelEditorSelection {
  from: number;
  to: number;
  text: string;
}

export interface NovelEditorHandle {
  /** 获取当前 HTML */
  getHTML: () => string;
  /** 获取当前纯文本 */
  getText: () => string;
  /** 替换整个内容（**纯文本**，用于切换章节） */
  setContent: (text: string) => void;
  /** 在末尾追加文本（流式生成用，批处理 + ProseMirror 事务）。
   *  适用于章节生成末尾追加场景。 */
  appendText: (text: string) => void;
  /** 选区重写入口：首次调用删掉 [from, originalTo] 选区，后续 delta 累加。
   *  - 每次传 **delta**（新增 chunk），不是累计全文
   *  - 内部用 rAF 批 flush（~60fps），不卡顿
   */
  replaceSelection: (from: number, originalTo: number, deltaText: string) => void;
  /** 替换指定 range（deprecated：见 replaceSelection） */
  replaceRange: (from: number, to: number, text: string) => void;
  /** 选中指定 range（高亮） */
  focus: () => void;
  /** 立即 flush 缓冲区（流式完成时调用） */
  flush: () => void;
}

interface Props {
  /** 正文内容（**纯文本**，`\n\n` 分段；章节切换时同步） */
  content: string;
  /** 内容变化回调（HTML 字符串） */
  onChange?: (html: string) => void;
  /** 选区变化回调（仅当有非空选区时触发） */
  onSelection?: (sel: NovelEditorSelection) => void;
  /** 可编辑 */
  editable?: boolean;
  /** 占位符 */
  placeholder?: string;
  className?: string;
}

// 批处理节流：每 16ms (~60fps) 最多刷一次
const FLUSH_INTERVAL_MS = 16;

const NovelEditor = forwardRef<NovelEditorHandle, Props>(function NovelEditor(
  {
    content,
    onChange,
    onSelection,
    editable = true,
    placeholder = "开始写章节正文……",
    className,
  },
  ref,
) {
  // 上次从外部灌进来的**纯文本**（用来判断"外部内容是不是变了"）
  const lastExternalTextRef = useRef<string>(content);
  // 流式追加的缓冲区
  const appendBufferRef = useRef<string>("");
  const flushTimerRef = useRef<number | null>(null);
  // 选区重写的缓冲区（{pending: 待插入的增量, insertPos: 插入位置}）
  const rewriteBufferRef = useRef<{ pending: string; insertPos: number } | null>(null);
  const rewriteTimerRef = useRef<number | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Selection.configure({ className: "selection" }),
      Placeholder.configure({ placeholder }),
    ],
    // ⚠️ 正文是**纯文本**（后端存的），必须先转成段落化 HTML ——
    //    直接丢给 Tiptap 会按 HTML 解析成一个大段落，段内 \n 渲染成空格
    //    → 整章挤成一行、字间全是空格。
    content: plainTextToParagraphHtml(content || ""),
    editable,
    onUpdate: ({ editor: ed }) => {
      onChange?.(ed.getHTML());
    },
    onSelectionUpdate: ({ editor: ed }) => {
      if (!onSelection) return;
      const { from, to } = ed.state.selection;
      if (from === to) return;
      const text = ed.state.doc.textBetween(from, to, "\n");
      onSelection({ from, to, text });
    },
    editorProps: {
      attributes: {
        class:
          "novel-editor-content focus:outline-none min-h-[400px] p-4",
        "data-placeholder": placeholder,
      },
    },
  });

  /** 立即 flush append 缓冲区（用 ProseMirror 事务一次插入） */
  const flushAppend = () => {
    if (!editor) return;
    const text = appendBufferRef.current;
    if (!text) return;
    appendBufferRef.current = "";
    flushTimerRef.current = null;

    // ProseMirror 事务：直接在末尾插入文本
    // 不调 chain() / focus()，避开完整 transaction
    const { view } = editor;
    if (!view) return;
    // ⚠️ 必须插到**最后一个段落内部**的末尾 —— 插在文档末尾会让
    //    ProseMirror 新建一个段落（每 16ms 一次 flush → 满篇假段落，
    //    用户库里那章就是 1012 个假段落，详见 AGENTS.md §4.11）。
    const pos = lastBlockEndPos(view.state.doc);
    // 模型给的 \n（段落分隔）在这里变成**真正的段落**
    const { tr } = insertWithParagraphBreaks(view.state.tr, pos, text);
    view.dispatch(tr);
  };

  /** 立即 flush rewrite 缓冲区（把待插入的增量插到重写位置） */
  const flushRewrite = () => {
    if (!editor) return;
    const buf = rewriteBufferRef.current;
    if (!buf || !buf.pending) return;
    rewriteTimerRef.current = null;

    const { view } = editor;
    if (!view) return;
    const { pending, insertPos } = buf;
    buf.pending = "";
    // ⚠️ **纯插入**，不覆盖任何已有内容。
    //    旧写法是 insertText(text, from, from + text.length) —— 那会把
    //    重写位置**后面**的正文一起替换掉（用户正文丢失），
    //    而且每次 flush 都会重复删除原选区。
    const tr = view.state.tr
      .insertText(pending, insertPos)
      .setMeta("addToHistory", false);
    view.dispatch(tr);
    // 插入位置后移（后续 delta 继续接在后面）
    buf.insertPos += pending.length;
  };

  useImperativeHandle(
    ref,
    (): NovelEditorHandle => ({
      getHTML: () => editor?.getHTML() ?? "",
      getText: () => editor?.getText() ?? "",
      setContent: (text: string) => {
        const plain = text || "";
        // ⚠️ 纯文本 → 段落化 HTML（否则整章变成一个段落，\n 渲染成空格）
        editor?.commands.setContent(plainTextToParagraphHtml(plain), {
          emitUpdate: false,
        });
        lastExternalTextRef.current = plain;
      },
      appendText: (text: string) => {
        if (!editor || !text) return;
        // 累加到缓冲区
        appendBufferRef.current += text;
        if (flushTimerRef.current === null) {
          flushTimerRef.current = window.setTimeout(flushAppend, FLUSH_INTERVAL_MS);
        }
      },
      replaceRange: (from: number, to: number, text: string) => {
        // 兼容旧调用：text 当作完整新文本替换（会整体替换，性能差）
        if (!editor || !text) return;
        const { view } = editor;
        if (!view) return;
        const tr = view.state.tr
          .insertText(text, from, to)
          .setMeta("addToHistory", false);
        view.dispatch(tr);
      },
      replaceSelection: (from: number, originalTo: number, deltaText: string) => {
        if (!editor || !deltaText) return;
        const { view } = editor;
        if (!view) return;
        // 首次调用：删掉原选区，记下插入位置（**只删一次**）
        if (!rewriteBufferRef.current) {
          rewriteBufferRef.current = { pending: "", insertPos: from };
          view.dispatch(view.state.tr.delete(from, originalTo));
        }
        // 后续：只累加**增量**（flush 时按 insertPos 逐段插入）
        rewriteBufferRef.current.pending += deltaText;
        if (rewriteTimerRef.current === null) {
          rewriteTimerRef.current = window.setTimeout(flushRewrite, FLUSH_INTERVAL_MS);
        }
      },
      focus: () => editor?.commands.focus(),
      flush: () => {
        if (flushTimerRef.current !== null) {
          clearTimeout(flushTimerRef.current);
          flushAppend();
        }
        if (rewriteTimerRef.current !== null) {
          clearTimeout(rewriteTimerRef.current);
          flushRewrite();
        }
      },
    }),
    [editor],
  );

  // 外部 content 变化时（章节切换）重置
  //
  // ⚠️ 比较的是**纯文本**，不是 HTML —— 早期版本拿 HTML 和纯文本比，
  //    两者永远不相等，行为全靠"effect 只在 content 变化时触发"兜着，
  //    很容易在重构时踩坑。
  useEffect(() => {
    if (!editor) return;
    const plain = content || "";
    if (plain !== lastExternalTextRef.current) {
      editor.commands.setContent(plainTextToParagraphHtml(plain), {
        emitUpdate: false,
      });
      lastExternalTextRef.current = plain;
    }
  }, [content, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(editable);
  }, [editable, editor]);

  // 卸载清理 timer
  useEffect(() => {
    return () => {
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
      }
      if (rewriteTimerRef.current !== null) {
        clearTimeout(rewriteTimerRef.current);
      }
    };
  }, []);

  return <EditorContent editor={editor} className={className} />;
});

export default NovelEditor;
