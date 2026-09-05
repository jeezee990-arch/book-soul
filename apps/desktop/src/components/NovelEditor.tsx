import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Selection } from "@tiptap/extensions";

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
  /** 替换整个内容（用于切换章节） */
  setContent: (html: string) => void;
  /** 在末尾追加文本（流式生成用，批处理 + ProseMirror 事务） */
  appendText: (text: string) => void;
  /** 替换指定 range（选区重写用） */
  replaceRange: (from: number, to: number, text: string) => void;
  /** 选中指定 range（高亮） */
  focus: () => void;
  /** 立即 flush 缓冲区（流式完成时调用） */
  flush: () => void;
}

interface Props {
  /** HTML 内容（章节切换时同步） */
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
  const lastContentRef = useRef<string>(content);
  // 流式追加的缓冲区
  const appendBufferRef = useRef<string>("");
  const flushTimerRef = useRef<number | null>(null);
  // 选区重写的缓冲区（{text, base_from, current_to}）
  const rewriteBufferRef = useRef<{ text: string; from: number } | null>(null);
  const rewriteTimerRef = useRef<number | null>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Selection.configure({ className: "selection" }),
    ],
    content: content || "",
    editable,
    onUpdate: ({ editor: ed }) => {
      const html = ed.getHTML();
      lastContentRef.current = html;
      onChange?.(html);
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
    const docSize = view.state.doc.content.size;
    const tr = view.state.tr.insertText(text, docSize);
    view.dispatch(tr);
  };

  /** 立即 flush rewrite 缓冲区（替换 [from, from+text.length]） */
  const flushRewrite = () => {
    if (!editor) return;
    const buf = rewriteBufferRef.current;
    if (!buf || !buf.text) return;
    rewriteBufferRef.current = null;
    rewriteTimerRef.current = null;

    const { view } = editor;
    if (!view) return;
    const { from } = buf;
    const to = from + buf.text.length;
    // 单次事务：替换 range
    const tr = view.state.tr
      .insertText(buf.text, from, to)
      // 强制同步 lastContentRef 给 onUpdate 触发
      .setMeta("addToHistory", false);
    view.dispatch(tr);
  };

  useImperativeHandle(
    ref,
    (): NovelEditorHandle => ({
      getHTML: () => editor?.getHTML() ?? "",
      getText: () => editor?.getText() ?? "",
      setContent: (html: string) => {
        editor?.commands.setContent(html || "", { emitUpdate: false });
        lastContentRef.current = html || "";
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
        if (!editor || !text) return;
        // 累加：每次 chunk 替换 [from, from + text.length]
        // 初次调用建 buffer，后续 chunk 直接替换扩展
        if (!rewriteBufferRef.current) {
          rewriteBufferRef.current = { text, from };
        } else {
          // 同一段选区：保留 from，扩展 text
          rewriteBufferRef.current.text += text;
        }
        // 移除原选区内容：把 [from, to] 替换为新 text
        if (rewriteBufferRef.current.text === text) {
          // 首次：删 [from, to]
          const { view } = editor;
          if (view) {
            view.dispatch(view.state.tr.delete(from, to));
          }
        }
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
  useEffect(() => {
    if (!editor) return;
    if (content !== lastContentRef.current) {
      editor.commands.setContent(content || "", { emitUpdate: false });
      lastContentRef.current = content || "";
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
