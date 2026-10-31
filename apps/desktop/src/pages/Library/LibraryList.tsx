/**
 * 作品卡片网格（素材库 · 作品 Tab）。
 *
 * 2026-10 UI 重设计：旧「作品库」有「作品」和「藏书馆」两个 Tab，
 * 唯一区别是"有没有章节"—— 对作者来说是同一个概念列表。
 * 现在合并为一份，用状态标签区分，藏书馆语义取消。
 *
 * 2026-10-30 补齐管理能力（用户实测反馈）：
 * - **右键菜单**：继续写 / 重命名 / 上移 / 下移 / 导出 / 删除
 * - **排序**：手动顺序（持久化在后端 sort_order）+ 最近更新 / 最近创建 / 字数 / 书名
 * - **删除**：二次确认（会级联删掉章节 / 人物卡 / 大纲）
 *
 * 字数 / 章数是后端 Novel 模型里没有的字段，这里异步补齐
 * （逐本拉章节列表汇总），不阻塞首屏渲染。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen } from "lucide-react";
import { toast } from "sonner";
import { novelsApi, downloadExportFile } from "@/api/novels";
import { chaptersApi } from "@/api/chapters";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useNovelsStore } from "@/stores/novels-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import NovelCard, { EMPTY_STAT, type NovelStat } from "./NovelCard";
import NovelContextMenu, { type NovelMenuState } from "./NovelContextMenu";
import { NovelConfirmDialog, NovelRenameDialog } from "./NovelDialogs";
import {
  NOVEL_SORT_OPTIONS,
  moveNovel,
  sortNovels,
  type NovelSortKey,
} from "./novel-sort";

interface Props {
  onSelect: (novel: Novel) => void;
  /** 继续写：切到写作页并选中该作品 */
  onContinue: (novel: Novel) => void;
}

/** 排序方式在 localStorage 里的键。 */
const SORT_KEY = "book-soul-library-works-sort";

/**
 * 读上次选的排序方式。
 *
 * @returns 排序方式（读不到或非法就回"手动顺序"）
 */
function loadSortKey(): NovelSortKey {
  try {
    const raw = localStorage.getItem(SORT_KEY);
    const hit = NOVEL_SORT_OPTIONS.find((o) => o.value === raw);
    return hit?.value ?? "manual";
  } catch {
    return "manual";
  }
}

export default function LibraryList({ onSelect, onContinue }: Props) {
  const [items, setItems] = useState<Novel[]>([]);
  const [stats, setStats] = useState<Record<number, NovelStat>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "writing" | "draft" | "imported">(
    "all",
  );
  const [sortKey, setSortKey] = useState<NovelSortKey>(loadSortKey);

  // 右键菜单 / 对话框
  const [menu, setMenu] = useState<NovelMenuState | null>(null);
  const [renameTarget, setRenameTarget] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Novel | null>(null);

  const refreshNovels = useNovelsStore((s) => s.refresh);
  const workspaceNovelId = useWorkspaceStore((s) => s.novelId);
  const setWorkspaceNovelId = useWorkspaceStore((s) => s.setNovelId);

  /** 拉列表 + 后台补章节统计。 */
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await novelsApi.list();
      setItems(data);
      setLoading(false);

      // 后台补齐章节统计（不阻塞首屏）
      void Promise.all(
        data.map(async (n) => {
          try {
            const chs = await chaptersApi.list(n.id);
            const stat: NovelStat = {
              words: chs.reduce((sum, c) => sum + c.word_count, 0),
              chapters: chs.length,
              written: chs.filter((c) => c.word_count > 0).length,
            };
            setStats((prev) => ({ ...prev, [n.id]: stat }));
          } catch {
            // 单本失败忽略
          }
        }),
      );
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setError(msg);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** 切换排序方式（记到 localStorage，下次进来还是这个）。 */
  function changeSort(next: NovelSortKey) {
    setSortKey(next);
    try {
      localStorage.setItem(SORT_KEY, next);
    } catch {
      // localStorage 不可用（隐私模式）时忽略
    }
  }

  async function handleExport(novel: Novel, format: "md" | "html" | "docx") {
    try {
      const file = await novelsApi.export(novel.id, format);
      downloadExportFile(file);
      toast.success("已开始下载", { description: file.filename });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("导出失败", { description: msg });
    }
  }

  // ===== 搜索 + 筛选 =====
  const matched = useMemo(() => {
    return items.filter((n) => {
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        if (
          !n.name.toLowerCase().includes(q) &&
          !n.genre.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      if (filter === "imported") return n.imported;
      if (filter === "draft") return !n.imported && n.status === "draft";
      if (filter === "writing") return !n.imported && n.status !== "draft";
      return true;
    });
  }, [items, query, filter]);

  /** 字数表（给"字数最多"排序用）。 */
  const wordCounts = useMemo(() => {
    const map: Record<number, number> = {};
    for (const [id, stat] of Object.entries(stats)) map[Number(id)] = stat.words;
    return map;
  }, [stats]);

  const filtered = useMemo(
    () => sortNovels(matched, sortKey, wordCounts),
    [matched, sortKey, wordCounts],
  );

  // ===== 右键菜单 =====

  /** 在指定坐标处打开某部作品的右键菜单。 */
  function openMenuAt(novel: Novel, x: number, y: number) {
    setMenu({ id: novel.id, x, y });
  }

  // ===== 重命名 =====

  function openRename(novel: Novel) {
    setRenameTarget({ id: novel.id, name: novel.name });
  }

  /**
   * 提交重命名。
   *
   * @param name 新名字；`null` 表示**用户取消**（不改任何数据）。
   */
  async function commitRename(name: string | null) {
    const target = renameTarget;
    setRenameTarget(null);
    if (!target || name === null) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    if (trimmed === target.name) return;
    try {
      const updated = await novelsApi.update(target.id, { name: trimmed });
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      void refreshNovels();
      toast.success("已重命名", { description: updated.name });
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        toast.error("已有同名作品", {
          description: `素材库里已经有《${trimmed}》，换个名字吧`,
        });
        return;
      }
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("重命名失败", { description: msg });
    }
  }

  // ===== 删除 =====

  async function commitDelete() {
    const target = deleteTarget;
    setDeleteTarget(null);
    if (!target) return;
    try {
      await novelsApi.remove(target.id);
      // 删掉的是当前选中的作品 → 清掉工作区选择（否则写作页会指向一本不存在的书）
      if (workspaceNovelId === target.id) {
        setWorkspaceNovelId(null);
      }
      await load();
      void refreshNovels();
      toast.success("已删除", { description: target.name });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("删除失败", { description: msg });
    }
  }

  // ===== 上移 / 下移 =====

  /**
   * 移动作品位置（手动顺序，持久化到后端）。
   *
   * @param id 要移动的作品 id
   * @param delta -1 上移，+1 下移
   */
  async function handleMove(id: number, delta: -1 | 1) {
    // 全量顺序 = 后端返回的顺序（已按 sort_order 排好）
    const allIds = items.map((n) => n.id);
    // 可见顺序 = 搜索/筛选/排序之后的顺序（用户看到的）
    const visibleIds = filtered.map((n) => n.id);
    const nextOrder = moveNovel(allIds, visibleIds, id, delta);
    if (!nextOrder) {
      toast.info(delta < 0 ? "已经在第一本了" : "已经在最后一本了");
      return;
    }
    try {
      await novelsApi.reorder(nextOrder);
      await load();
      // 手动顺序和"按其它字段排"是互斥的 —— 移动后切回手动顺序，
      // 否则用户会以为"点了没反应"（列表顺序没变）。
      if (sortKey !== "manual") {
        changeSort("manual");
        toast.success("已移动", { description: "已切换到「手动顺序」" });
      } else {
        toast.success("已移动");
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("排序保存失败", { description: msg });
    }
  }

  // 右键菜单的目标作品（用于判断上/下移是否到边界）
  const menuNovel = menu ? (items.find((n) => n.id === menu.id) ?? null) : null;
  const menuIndex = menuNovel ? filtered.findIndex((n) => n.id === menuNovel.id) : -1;

  return (
    <div>
      {/* 搜索 + 筛选 + 排序 */}
      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <div className="relative w-[280px]">
          <svg
            viewBox="0 0 24 24"
            className="absolute top-2 left-2.5 h-[15px] w-[15px] text-neutral-400"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4-4" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索作品名、题材…"
            className="h-8 w-full rounded-lg border border-neutral-200 bg-white pr-2.5 pl-8.5 text-[12.5px] outline-none focus:border-indigo-500/50 dark:border-neutral-800 dark:bg-neutral-900"
            style={{ paddingLeft: "2.1rem" }}
          />
        </div>
        <div className="flex gap-0.5 rounded-lg border border-neutral-200 bg-neutral-50 p-0.5 dark:border-neutral-800 dark:bg-neutral-800/40">
          {(
            [
              { v: "all", t: "全部" },
              { v: "writing", t: "连载中" },
              { v: "draft", t: "草稿" },
              { v: "imported", t: "已导入" },
            ] as const
          ).map((o) => (
            <button
              key={o.v}
              type="button"
              onClick={() => setFilter(o.v)}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-[11.5px] transition-colors",
                filter === o.v
                  ? "bg-white font-medium shadow-sm dark:bg-neutral-700 dark:text-neutral-50"
                  : "text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200",
              )}
            >
              {o.t}
            </button>
          ))}
        </div>

        {/* 排序（2026-10-30 新增） */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11.5px] text-neutral-400">排序</span>
          <Select value={sortKey} onValueChange={(v) => changeSort(v as NovelSortKey)}>
            <SelectTrigger className="h-8 w-[7.5rem] text-[12px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {NOVEL_SORT_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <span className="ml-auto text-[11.5px] text-neutral-400">
          共 {filtered.length} 部
        </span>
      </div>

      {error ? (
        <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[12px] text-rose-500">
          加载失败：{error}
        </p>
      ) : null}

      {loading ? (
        <div className="grid grid-cols-4 gap-3">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div
              key={i}
              className="h-[186px] animate-pulse rounded-xl bg-neutral-100 dark:bg-neutral-800/60"
            />
          ))}
        </div>
      ) : null}

      {!loading && filtered.length === 0 ? (
        <div className="py-16 text-center">
          <BookOpen className="mx-auto mb-2.5 h-7 w-7 text-neutral-300 dark:text-neutral-700" />
          <p className="text-[13px] text-neutral-400">还没有作品</p>
          <p className="mt-1 text-[11.5px] text-neutral-400">
            去「开新书」走一遍三步流程，或从「导入」接入本地小说
          </p>
        </div>
      ) : null}

      {!loading && filtered.length > 0 ? (
        <div className="grid grid-cols-4 gap-3">
          {filtered.map((n) => (
            <NovelCard
              key={n.id}
              novel={n}
              stat={stats[n.id] ?? EMPTY_STAT}
              onOpen={onSelect}
              onContinue={onContinue}
              onExport={(novel, fmt) => void handleExport(novel, fmt)}
              onMenu={openMenuAt}
            />
          ))}
        </div>
      ) : null}

      {/* 右键菜单（2026-10-30 新增） */}
      <NovelContextMenu
        state={menu}
        atTop={menuIndex <= 0}
        atBottom={menuIndex < 0 || menuIndex >= filtered.length - 1}
        onClose={() => setMenu(null)}
        onContinue={(id) => {
          const n = items.find((i) => i.id === id);
          if (n) onContinue(n);
        }}
        onRename={(id) => {
          const n = items.find((i) => i.id === id);
          if (n) openRename(n);
        }}
        onMoveUp={(id) => void handleMove(id, -1)}
        onMoveDown={(id) => void handleMove(id, 1)}
        onExport={(id, format) => {
          const n = items.find((i) => i.id === id);
          if (n) void handleExport(n, format);
        }}
        onDelete={(id) => {
          const n = items.find((i) => i.id === id);
          if (n) setDeleteTarget(n);
        }}
      />

      {/* 重命名对话框 */}
      <NovelRenameDialog
        open={renameTarget !== null}
        initialName={renameTarget?.name ?? ""}
        onSubmit={(name) => void commitRename(name)}
      />

      {/* 删除确认 */}
      <NovelConfirmDialog
        open={deleteTarget !== null}
        title="删除作品"
        description={
          deleteTarget
            ? `将删除《${deleteTarget.name}》及其全部章节、人物卡、大纲，此操作不可恢复。`
            : ""
        }
        onConfirm={() => void commitDelete()}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
