/**
 * 种子库管理弹窗（需求6）。
 *
 * 干什么：
 * - 顶部**板块选择器**（修仙 / 都市 / …）：一次只管一个板块，写操作只写那一个 YAML
 * - 主体：该板块的全部种子词，按分类分组；每行可编辑 / 删除
 * - 工具栏：「管理」开关（勾选 + 批量删除）、「添加」、「导入」
 *
 * 交互约束：
 * - 切换板块 → 列表**完全替换**（不混板块），选择状态清空
 * - 任何写操作成功 → 通知外层刷新候选词（``onChanged``）
 *
 * 列表区与导入面板拆到独立文件（见 wordbank-manager-list / -import），
 * 本文件只管状态与编排。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Library, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { importWordbankFile, wordbanksApi } from "@/api/wordbanks";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import type { WordbankAllWords, WordbankListEntry } from "@/lib/types";
import { categoryLabel, genreLabel, parseImportText, summarizeImport } from "./wordbank-parse";
import WordbankManagerImport from "./wordbank-manager-import";
import WordbankManagerList from "./wordbank-manager-list";
import {
  clearSelection,
  selectedItems,
  selectionCount,
  toggleSelection,
} from "./wordbank-selection";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 当前向导选中的板块（默认高亮） */
  genreId?: string | null;
  /** 词库有变动 → 通知外层刷新候选词 */
  onChanged?: () => void;
}

/** 错误信息统一成一句话。 */
function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function WordbankManagerDialog({
  open,
  onOpenChange,
  genreId = null,
  onChanged,
}: Props) {
  const [genres, setGenres] = useState<WordbankListEntry[]>([]);
  const [active, setActive] = useState("");
  const [data, setData] = useState<WordbankAllWords | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  const [manage, setManage] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [adding, setAdding] = useState(false);
  const [newWord, setNewWord] = useState("");
  const [newCategory, setNewCategory] = useState("themes");

  const [editing, setEditing] = useState<{ category: string; word: string } | null>(null);
  const [editValue, setEditValue] = useState("");

  const [importing, setImporting] = useState(false);
  const [importText, setImportText] = useState("");
  const [importCategory, setImportCategory] = useState("themes");
  const [importStats, setImportStats] = useState<string | null>(null);
  const [importErrors, setImportErrors] = useState<string[]>([]);

  const categories = useMemo(() => data?.categories ?? [], [data]);

  /** 拉板块列表（来自后端 —— config/wordbanks 下实际存在的板块）。 */
  const loadGenres = useCallback(async () => {
    try {
      const list = await wordbanksApi.list();
      setGenres(list.genres);
      setActive((prev) => {
        if (prev && list.genres.some((g) => g.id === prev)) return prev;
        if (genreId && list.genres.some((g) => g.id === genreId)) return genreId;
        return list.genres[0]?.id ?? "";
      });
    } catch (e: unknown) {
      toast.error("加载词库板块失败", { description: errText(e) });
    }
  }, [genreId]);

  /** 拉当前板块的全部词。 */
  const loadWords = useCallback(async (gid: string) => {
    if (!gid) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      setData(await wordbanksApi.getAllWords(gid));
    } catch (e: unknown) {
      toast.error("加载词库失败", { description: errText(e) });
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) void loadGenres();
  }, [open, loadGenres]);

  // 切换板块 → 列表完全替换，选择 / 编辑 / 表单状态全部清空
  useEffect(() => {
    if (!open || !active) return;
    setSelected(clearSelection());
    setEditing(null);
    setAdding(false);
    setImporting(false);
    setImportStats(null);
    setImportErrors([]);
    void loadWords(active);
  }, [open, active, loadWords]);

  /** 写操作成功后：刷新列表 + 通知外层刷新候选词。 */
  const afterWrite = useCallback(async () => {
    await loadWords(active);
    onChanged?.();
  }, [active, loadWords, onChanged]);

  const handleAdd = useCallback(async () => {
    const word = newWord.trim();
    if (!word) {
      toast.error("请输入词条");
      return;
    }
    setBusy(true);
    try {
      const res = await wordbanksApi.addWords(active, [{ category: newCategory, word }]);
      if (res.errors.length > 0) {
        toast.error("添加失败", { description: res.errors.join("；") });
      } else if (res.added === 0) {
        toast.warning("词条已存在", { description: "该分类下已经有这个词了" });
      } else {
        toast.success("已添加「" + word + "」");
      }
      setNewWord("");
      setAdding(false);
      await afterWrite();
    } catch (e: unknown) {
      toast.error("添加失败", { description: errText(e) });
    } finally {
      setBusy(false);
    }
  }, [active, newWord, newCategory, afterWrite]);

  const handleSaveEdit = useCallback(async () => {
    if (!editing) return;
    const next = editValue.trim();
    if (!next) {
      toast.error("新词条不能为空");
      return;
    }
    setBusy(true);
    try {
      await wordbanksApi.updateWord(active, editing.category, editing.word, next);
      toast.success("已修改");
      setEditing(null);
      await afterWrite();
    } catch (e: unknown) {
      toast.error("修改失败", { description: errText(e) });
    } finally {
      setBusy(false);
    }
  }, [active, editing, editValue, afterWrite]);

  const handleDelete = useCallback(
    async (items: { category: string; word: string }[]) => {
      if (items.length === 0) return;
      setBusy(true);
      try {
        const res = await wordbanksApi.deleteWords(active, items);
        if (res.deleted > 0) {
          toast.success("已删除 " + res.deleted + " 个词条");
        }
        if (res.missing.length > 0) {
          toast.warning("有词条没找到", { description: res.missing.join("、") });
        }
        setSelected(clearSelection());
        await afterWrite();
      } catch (e: unknown) {
        toast.error("删除失败", { description: errText(e) });
      } finally {
        setBusy(false);
      }
    },
    [active, afterWrite],
  );

  /** 导入结果 → 统计文案。 */
  const showImportResult = useCallback((res: { added: number; duplicates: number; failed: number; errors: string[] }) => {
    setImportStats("新增 " + res.added + " · 重复 " + res.duplicates + " · 失败 " + res.failed);
    setImportErrors(res.errors);
    if (res.added > 0) {
      toast.success("导入完成，新增 " + res.added + " 个词条");
    } else {
      toast.warning("没有新增词条", { description: "可能都重复了" });
    }
  }, []);

  const handleImportText = useCallback(async () => {
    if (!importText.trim()) {
      toast.error("请先粘贴要导入的文本");
      return;
    }
    setBusy(true);
    try {
      const res = await wordbanksApi.importText(active, importText, importCategory);
      showImportResult(res);
      await afterWrite();
    } catch (e: unknown) {
      toast.error("导入失败", { description: errText(e) });
    } finally {
      setBusy(false);
    }
  }, [active, importText, importCategory, showImportResult, afterWrite]);

  const handleImportFile = useCallback(
    async (file: File) => {
      setBusy(true);
      try {
        const res = await importWordbankFile(active, file, importCategory);
        showImportResult(res);
        await afterWrite();
      } catch (e: unknown) {
        toast.error("导入失败", { description: errText(e) });
      } finally {
        setBusy(false);
      }
    },
    [active, importCategory, showImportResult, afterWrite],
  );

  /** 导入预览（前端预解析，后端才是权威）。 */
  const preview = useMemo(
    () => summarizeImport(parseImportText(importText, importCategory, categories)),
    [importText, importCategory, categories],
  );

  const selectedCount = selectionCount(selected);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[86vh] max-w-3xl flex-col gap-3 overflow-hidden p-5">
        <DialogHeader className="shrink-0">
          <DialogTitle className="text-[15px]">种子库管理</DialogTitle>
          <DialogDescription className="text-[11.5px]">
            按板块管理种子词 —— 改动只写当前板块自己的词库文件
          </DialogDescription>
        </DialogHeader>

        {/* 板块选择器 */}
        <div className="flex shrink-0 flex-wrap gap-1.5">
          {genres.length === 0 ? (
            <span className="text-[11.5px] text-neutral-400">没有可用板块</span>
          ) : (
            genres.map((g) => {
              const on = g.id === active;
              return (
                <button
                  key={g.id}
                  type="button"
                  onClick={() => setActive(g.id)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[12px] transition-colors",
                    on
                      ? "border-indigo-500 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300"
                      : "border-neutral-200 text-neutral-600 hover:bg-neutral-50 dark:border-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-900",
                  )}
                >
                  {genreLabel(g.id, g.name)}
                  <span className="text-[10.5px] text-neutral-400">{g.total}</span>
                </button>
              );
            })
          )}
        </div>

        {/* 工具栏 */}
        <div className="flex shrink-0 items-center justify-between gap-2 border-y border-neutral-200 py-2 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            <Switch checked={manage} onCheckedChange={setManage} aria-label="管理模式" />
            <span className="text-[12px] text-neutral-600 dark:text-neutral-300">管理</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11.5px]"
              onClick={() => {
                setAdding((v) => !v);
                setImporting(false);
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              添加
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[11.5px]"
              onClick={() => {
                setImporting((v) => !v);
                setAdding(false);
              }}
            >
              <Library className="h-3.5 w-3.5" />
              导入
            </Button>
          </div>
        </div>

        {/* 添加表单 */}
        {adding ? (
          <div className="flex shrink-0 items-center gap-2 rounded-lg border border-neutral-200 p-2 dark:border-neutral-800">
            <Input
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
              placeholder="新词条（例：破境丹）"
              className="h-8 text-[12px]"
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleAdd();
              }}
            />
            <Select value={newCategory} onValueChange={setNewCategory}>
              <SelectTrigger className="h-8 w-28 text-[12px]">
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
              className="h-8 text-[12px]"
              disabled={busy}
              onClick={() => void handleAdd()}
            >
              确定
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 px-2 text-[12px]"
              onClick={() => setAdding(false)}
            >
              取消
            </Button>
          </div>
        ) : null}

        {/* 导入面板 */}
        {importing ? (
          <WordbankManagerImport
            text={importText}
            onTextChange={setImportText}
            category={importCategory}
            onCategoryChange={setImportCategory}
            categories={categories}
            busy={busy}
            stats={importStats}
            errors={importErrors}
            preview={preview}
            onImportText={() => void handleImportText()}
            onImportFile={(f) => void handleImportFile(f)}
          />
        ) : null}

        {/* 词条列表 */}
        <div className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
          {data ? (
            <WordbankManagerList
              data={data}
              loading={loading}
              manage={manage}
              selected={selected}
              editing={editing}
              editValue={editValue}
              busy={busy}
              onToggleSelect={(key) => setSelected((prev) => toggleSelection(prev, key))}
              onStartEdit={(category, word) => {
                setEditing({ category, word });
                setEditValue(word);
              }}
              onEditValueChange={setEditValue}
              onSaveEdit={() => void handleSaveEdit()}
              onCancelEdit={() => setEditing(null)}
              onDelete={(category, word) => void handleDelete([{ category, word }])}
            />
          ) : null}
        </div>

        {/* 批量管理底栏 */}
        {manage ? (
          <div className="flex shrink-0 items-center justify-between border-t border-neutral-200 pt-2 dark:border-neutral-800">
            <span className="text-[11.5px] text-neutral-500">已选 {selectedCount} 项</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className="h-7 px-2 text-[11.5px]"
                disabled={busy || selectedCount === 0}
                onClick={() => void handleDelete(selectedItems(selected))}
              >
                <Trash2 className="h-3.5 w-3.5" />
                批量删除
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-[11.5px]"
                onClick={() => {
                  setManage(false);
                  setSelected(clearSelection());
                }}
              >
                退出管理
              </Button>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
