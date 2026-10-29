/**
 * 种子库管理的导入面板（粘贴文本 + 选文件 + 解析统计）。
 *
 * 前端先预解析一遍给用户看"会导入多少条、哪几行有问题"，
 * 真正落库由后端再解析一次（后端才是权威）。
 */

import { FileUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { categoryLabel } from "./wordbank-parse";

interface Props {
  /** 待导入文本 */
  text: string;
  onTextChange: (value: string) => void;
  /** 没写分类前缀的词归到哪类 */
  category: string;
  onCategoryChange: (value: string) => void;
  /** 当前板块的分类列表 */
  categories: string[];
  /** 有写操作在进行中 */
  busy: boolean;
  /** 上一次导入的统计（新增 / 重复 / 失败） */
  stats: string | null;
  /** 上一次导入的失败行明细 */
  errors: string[];
  /** 预解析摘要 */
  preview: string;
  onImportText: () => void;
  onImportFile: (file: File) => void;
}

export default function WordbankManagerImport({
  text,
  onTextChange,
  category,
  onCategoryChange,
  categories,
  busy,
  stats,
  errors,
  preview,
  onImportText,
  onImportFile,
}: Props) {
  return (
    <div className="shrink-0 space-y-2 rounded-lg border border-neutral-200 p-2 dark:border-neutral-800">
      <Textarea
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder={"每行一个词，或用逗号分隔\n也支持「主题:逆袭」这种分类前缀"}
        className="h-24 text-[12px]"
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11.5px] text-neutral-400">默认分类</span>
        <Select value={category} onValueChange={onCategoryChange}>
          <SelectTrigger className="h-7 w-28 text-[11.5px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>
                {categoryLabel(c)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          size="sm"
          className="h-7 text-[11.5px]"
          disabled={busy}
          onClick={onImportText}
        >
          导入文本
        </Button>
        <label className="inline-flex h-7 cursor-pointer items-center gap-1 rounded-md border border-input px-2 text-[11.5px] hover:bg-accent">
          <FileUp className="h-3.5 w-3.5" />
          选文件
          <input
            type="file"
            accept=".txt,.md,.csv,.json,text/plain"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) onImportFile(file);
            }}
          />
        </label>
        <span className="text-[11px] text-neutral-400">{preview}</span>
      </div>
      {stats ? (
        <p className="text-[11.5px] text-emerald-600 dark:text-emerald-400">{stats}</p>
      ) : null}
      {errors.length > 0 ? (
        <ul className="max-h-20 space-y-0.5 overflow-y-auto text-[11px] text-amber-600 dark:text-amber-400">
          {errors.map((e, i) => (
            <li key={i}>· {e}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
