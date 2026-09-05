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
  /** 在末尾追加文本（流式生成用） */
  appendText: (text: string) => void;
  /** 替换指定 range（选区重写用） */
  replaceRange: (from: number, to: number, text: string) => void;
  /** 选中指定 range（高亮） */
  focus: () => void;
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

/** Tiptap 富文本编辑器（Phase 4.2 + 4.3 + 4.4）。
 *
 * 通过 ref 暴露 imperative API 用于流式追加 / 选区替换，避开 React 重渲染瓶颈。
 */
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
  // 内部"受控开关"：流式更新时不希望外部 onChange 触发
  const silentRef = useRef<boolean>(false);

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
      if (silentRef.current) return;
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

  useImperativeHandle(
    ref,
    (): NovelEditorHandle => ({
      getHTML: () => editor?.getHTML() ?? "",
      getText: () => editor?.getText() ?? "",
      setContent: (html: string) => {
        silentRef.current = true;
        editor?.commands.setContent(html || "", { emitUpdate: false });
        lastContentRef.current = html || "";
        silentRef.current = false;
      },
      appendText: (text: string) => {
        if (!editor || !text) return;
        silentRef.current = true;
        // 在文档末尾插入
        const docSize = editor.state.doc.content.size;
        editor.chain().focus("end").insertContentAt(docSize, text).run();
        silentRef.current = false;
      },
      replaceRange: (from: number, to: number, text: string) => {
        if (!editor) return;
        silentRef.current = true;
        editor
          .chain()
          .focus()
          .setTextSelection({ from, to })
          .insertContent(text)
          .run();
        silentRef.current = false;
      },
      focus: () => editor?.commands.focus(),
    }),
    [editor],
  );

  // 外部 content 变化时（章节切换）重置
  useEffect(() => {
    if (!editor) return;
    if (content !== lastContentRef.current) {
      silentRef.current = true;
      editor.commands.setContent(content || "", { emitUpdate: false });
      lastContentRef.current = content || "";
      silentRef.current = false;
    }
  }, [content, editor]);

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(editable);
  }, [editable, editor]);

  return <EditorContent editor={editor} className={className} />;
});

export default NovelEditor;
