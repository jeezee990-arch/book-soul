import { useState } from "react";
import { Send, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type PromptBoxAction = "generate" | "rewrite" | "refine";

interface Props {
  /** 行为：决定按钮 label 和默认 placeholder */
  action: PromptBoxAction;
  /** 提交时回调（用户输入文本） */
  onSubmit: (prompt: string) => void | Promise<void>;
  /** 可选：清除提示词 */
  onClear?: () => void;
  /** 流式生成中：禁用输入和提交 */
  busy?: boolean;
  /** 标题（可选；如"AI 重写要求"） */
  title?: string;
  /** 占位符 */
  placeholder?: string;
  /** 自定义类名 */
  className?: string;
}

const ACTION_LABEL: Record<PromptBoxAction, string> = {
  generate: "生成",
  rewrite: "重写",
  refine: "润色",
};

const ACTION_ICON: Record<PromptBoxAction, typeof Sparkles> = {
  generate: Sparkles,
  rewrite: Sparkles,
  refine: Sparkles,
};

const DEFAULT_PLACEHOLDER: Record<PromptBoxAction, string> = {
  generate: "可输入额外要求：希望重点写战斗 / 心理 / 对话...",
  rewrite: "描述改写要求：更紧凑 / 换对话风格 / 补心理活动...",
  refine: "描述润色方向：增强文笔 / 简化表达 / 调整节奏...",
};

/** 共享提示词输入框（Phase 4.5）。
 *
 * 用途：
 * - 创作页：流式生成、选段/全文重写
 * - 灵感园：重新生成大纲
 *
 * 设计：受控的 Textarea + 主操作按钮 + 可选 clear。
 * 行为由 `action` 决定（按钮 label / 占位符）。
 */
export default function PromptBox({
  action,
  onSubmit,
  onClear,
  busy = false,
  title,
  placeholder,
  className,
}: Props) {
  const [value, setValue] = useState("");

  async function handleSubmit() {
    const text = value.trim();
    if (!text) return;
    await onSubmit(text);
    setValue("");
  }

  const Icon = ACTION_ICON[action];
  const label = ACTION_LABEL[action];
  const ph = placeholder ?? DEFAULT_PLACEHOLDER[action];

  return (
    <div
      className={cn(
        "rounded-md border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-950 p-3 space-y-2",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-medium text-neutral-600 dark:text-neutral-400">
          <Icon className="h-3.5 w-3.5" />
          <span>{title ?? `AI ${label}要求`}</span>
        </div>
        {value && onClear && !busy && (
          <button
            onClick={() => {
              setValue("");
              onClear();
            }}
            className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
            aria-label="清除"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={ph}
        rows={2}
        maxLength={2000}
        disabled={busy}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            void handleSubmit();
          }
        }}
        className="min-h-[60px] resize-y text-sm"
      />
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-neutral-400">⌘/Ctrl + Enter 提交</span>
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={busy || !value.trim()}
          className="h-7 px-3"
        >
          <Send className="mr-1.5 h-3 w-3" />
          {busy ? "处理中…" : label}
        </Button>
      </div>
    </div>
  );
}
