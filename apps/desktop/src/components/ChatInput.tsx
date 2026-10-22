/** 底部固定的作者输入框（Phase 4 / 任务 4）。
 *
 * 设计：
 * - 全局唯一底部固定，所有页面可见
 * - 占位提示当前所在步骤会附加到 prompt 的 "user_extra"
 * - 按 Enter 发送；Shift+Enter 换行
 * - 发送时把内容推给上层；上层负责把它塞进 LLM 请求
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface ChatInputHandle {
  /** 设置值（外部程序化更新时用，比如"清空"） */
  setValue: (v: string) => void;
  /** 当前值 */
  getValue: () => string;
}

interface Props {
  /** 提交回调（按 Enter 触发） */
  onSubmit?: (text: string) => void;
  /** 占位符（根据步骤变化） */
  placeholder?: string;
  /** 是否禁用（生成中） */
  disabled?: boolean;
  /** 默认值（外部程序化同步） */
  value?: string;
  /** 自定义 className */
  className?: string;
}

export default function ChatInput({
  onSubmit,
  placeholder = "输入消息... (输入 / 唤起命令)",
  disabled = false,
  value,
  className = "",
}: Props) {
  const [text, setText] = useState(value ?? "");
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // 外部 value 同步（受控用）
  useEffect(() => {
    if (value !== undefined && value !== text) {
      setText(value);
    }
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSubmit?.(trimmed);
    setText("");
  }, [text, disabled, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-30 px-6 pb-5 pt-3 bg-gradient-to-t from-white via-white/95 to-white/0 dark:from-neutral-950 dark:via-neutral-950/95 dark:to-neutral-950/0 ${className}`}
    >
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-sm px-4 py-3 focus-within:border-neutral-300 dark:focus-within:border-neutral-700 transition-colors">
          <textarea
            ref={taRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-neutral-400 dark:placeholder:text-neutral-500 disabled:opacity-50 max-h-40 overflow-y-auto"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="shrink-0 w-9 h-9 rounded-full bg-neutral-200 dark:bg-neutral-800 text-neutral-500 dark:text-neutral-400 flex items-center justify-center transition-all hover:bg-neutral-300 dark:hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="发送"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="w-4 h-4"
            >
              <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}