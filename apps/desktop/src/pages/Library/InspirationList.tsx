/**
 * 灵感库列表（2026-10-29 重做：右键菜单 + 批量管理 + 长按拖动排序）。
 *
 * 三块新能力：
 * 1. **右键菜单**：重命名 / 删除 / 置顶（取消置顶）
 * 2. **管理模式**：标题栏「管理」按钮 → 勾选 → 底部「批量删除」
 * 3. **长按拖动排序**：按住左键 ≥300ms 或按住移动超阈值 → 进入拖拽态，
 *    松手提交新顺序（后端按 id 顺序重排 sort_order）
 *
 * ⚠️ 排序铁律：置顶项永远排在最前（后端 `pinned DESC, sort_order ASC`），
 * 所以拖拽**不跨组** —— 否则用户拖了没反应，以为功能坏了。
 * 详见 `./inspiration-manage.ts` 的纯逻辑。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ListChecks, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import EmptyState from "@/components/layout/EmptyState";
import { inspirationsApi } from "@/api/inspirations";
import type { InspirationDetail } from "@/api/inspirations";
import { novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { Inspiration, Novel } from "@/lib/types";
import InspirationCard from "./InspirationCard";
import InspirationContextMenu, {
  type ContextMenuState,
} from "./InspirationContextMenu";
import { InspirationConfirmDialog, InspirationRenameDialog } from "./InspirationDialogs";
import {
  computeReorderedIds,
  deriveInspirationTitle,
  resolveRenamePayload,
  togglePinned,
  toggleSelected,
} from "./inspiration-manage";

/** 长按多久进入拖拽态（毫秒）。 */
const LONG_PRESS_MS = 300;
/** 按住移动超过这个距离（像素）也直接进入拖拽态。 */
const MOVE_THRESHOLD_PX = 8;
/** 算全局顺序时拉多少条（后端上限 500）。 */
const GLOBAL_LIST_LIMIT = 500;

interface Props {
  typeFilter: string | null;
  onTypeFilterChange: (v: string | null) => void;
  onSelect: (detail: InspirationDetail) => void;
}

/**
 * 灵感库列表。
 *
 * @param props - 组件属性
 */
export default function InspirationList({
  typeFilter,
  onTypeFilterChange,
  onSelect,
}: Props) {
  const [items, setItems] = useState<Inspiration[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 管理模式
  const [manageMode, setManageMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // 右键菜单 / 对话框
  const [menu, setMenu] = useState<ContextMenuState | null>(null);
  const [renameTarget, setRenameTarget] = useState<{
    id: number;
    title: string;
  } | null>(null);
  const [confirm, setConfirm] = useState<{ ids: number[] } | null>(null);

  // 拖拽
  const [dragId, setDragId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<{
    id: number;
    after: boolean;
  } | null>(null);

  const pressRef = useRef<{ id: number; startX: number; startY: number } | null>(
    null,
  );
  const longPressTimer = useRef<number | null>(null);
  const pointerPos = useRef({ x: 0, y: 0 });
  /** 拖拽中的 id（同步版本 —— setState 是异步的，指针事件里必须读同步值）。 */
  const dragIdRef = useRef<number | null>(null);
  /** 拖拽结束时的清理函数（卸载时用）。 */
  const teardownRef = useRef<(() => void) | null>(null);
  /** 上次拖拽结束的时间戳 —— 用来吃掉拖拽后紧跟的那次 click。 */
  const lastDragEndAt = useRef(0);

  // 组件卸载时把挂在 window 上的指针监听摘掉
  useEffect(() => {
    return () => {
      teardownRef.current?.();
      if (longPressTimer.current !== null) {
        window.clearTimeout(longPressTimer.current);
      }
    };
  }, []);

  /** 拉取列表。 */
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [insps, nvs] = await Promise.all([
        inspirationsApi.list(typeFilter ? { type: typeFilter } : undefined),
        novelsApi.list(),
      ]);
      setItems(insps);
      setNovels(nvs);
    } catch (e: unknown) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [typeFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const novelNameById = new Map(novels.map((n) => [n.id, n.name] as const));

  /** 把错误消息统一成可读文本。 */
  function errText(e: unknown): string {
    return e instanceof ApiError ? e.message : String(e);
  }

  // ===== 详情 =====

  async function handleOpen(ins: Inspiration) {
    // 拖拽刚结束时，紧跟的那次 click 要吃掉（别顺手打开详情）
    if (Date.now() - lastDragEndAt.current < 300) return;
    try {
      onSelect(await inspirationsApi.detail(ins.id));
    } catch (e: unknown) {
      toast.error("加载详情失败", { description: errText(e) });
    }
  }

  // ===== 右键菜单 =====

  function handleContextMenu(e: React.MouseEvent, ins: Inspiration) {
    e.preventDefault();
    e.stopPropagation();
    if (manageMode) return;
    setMenu({ id: ins.id, x: e.clientX, y: e.clientY });
  }

  // ===== 重命名 =====

  function openRename(ins: Inspiration) {
    setRenameTarget({
      id: ins.id,
      title: ins.title ?? deriveInspirationTitle(ins),
    });
  }

  /**
   * 提交重命名。
   *
   * @param title 新标题；`null` 表示用户**取消**（不改任何数据）。
   *   空串表示"保存但清空标题"（回落到自动摘要）。
   */
  async function commitRename(title: string | null) {
    const target = renameTarget;
    setRenameTarget(null);
    // ⚠️ 2026-10-29 评审：取消 / ESC / 点遮罩都会走到这里 ——
    //    以前一律传 ""，等于"保存空标题" → 用户自定义标题被**静默清空**。
    //    现在 null = 取消，直接返回，一个字节都不改。
    if (!target) return;
    const payload = resolveRenamePayload(title);
    if (payload === null) return;
    try {
      const updated = await inspirationsApi.update(target.id, payload);
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      toast.success(payload.title ? "已重命名" : "已恢复自动摘要");
    } catch (e: unknown) {
      toast.error("重命名失败", { description: errText(e) });
    }
  }

  // ===== 置顶 =====

  async function handleTogglePin(ins: Inspiration) {
    try {
      await inspirationsApi.update(ins.id, { pinned: togglePinned(ins.pinned) });
      // 置顶会改变列表顺序（置顶项排最前）→ 重新拉一次，保证与后端一致
      await load();
      toast.success(ins.pinned ? "已取消置顶" : "已置顶");
    } catch (e: unknown) {
      toast.error("操作失败", { description: errText(e) });
    }
  }

  // ===== 删除 =====

  function askDelete(ins: Inspiration) {
    setConfirm({ ids: [ins.id] });
  }

  async function commitDelete() {
    const target = confirm;
    setConfirm(null);
    if (!target || target.ids.length === 0) return;
    try {
      if (target.ids.length === 1) {
        await inspirationsApi.remove(target.ids[0]);
      } else {
        await inspirationsApi.batchDelete(target.ids);
      }
      setSelected((prev) => {
        const next = new Set(prev);
        target.ids.forEach((id) => next.delete(id));
        return next;
      });
      await load();
      toast.success(
        target.ids.length > 1 ? `已删除 ${target.ids.length} 项` : "已删除",
      );
    } catch (e: unknown) {
      toast.error("删除失败", { description: errText(e) });
    }
  }

  // ===== 批量管理 =====

  function toggleManageMode() {
    setManageMode((m) => !m);
    setSelected(new Set());
  }

  function handleToggleSelect(ins: Inspiration) {
    setSelected((prev) => toggleSelected(prev, ins.id));
  }

  function askBatchDelete() {
    if (selected.size === 0) return;
    setConfirm({ ids: Array.from(selected) });
  }

  // ===== 长按拖动排序 =====

  /** 命中测试：找鼠标下面的条目，以及落在它的上半还是下半。 */
  function hitTest(
    x: number,
    y: number,
    excludeId: number,
  ): { id: number; after: boolean } | null {
    const el = document.elementFromPoint(x, y);
    const card = el?.closest?.("[data-inspiration-id]") as HTMLElement | null;
    if (!card) return null;
    const id = Number(card.getAttribute("data-inspiration-id"));
    if (!Number.isFinite(id) || id === excludeId) return null;
    const rect = card.getBoundingClientRect();
    return { id, after: y > rect.top + rect.height / 2 };
  }

  function clearLongPress() {
    if (longPressTimer.current !== null) {
      window.clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }

  function handleCardPointerDown(e: React.PointerEvent, ins: Inspiration) {
    if (manageMode) return; // 管理模式不拖拽
    if (e.button !== 0) return; // 只认左键
    // 上一轮拖拽的残留监听先摘掉
    teardownRef.current?.();

    const press = { id: ins.id, startX: e.clientX, startY: e.clientY };
    pressRef.current = press;
    pointerPos.current = { x: e.clientX, y: e.clientY };

    // ⚠️ 监听直接挂在 pointerdown 里挂 —— 不能靠 useEffect：
    // 按下时没有 setState，不触发重渲染，effect 不会跑，监听就挂不上，
    // 第一段移动会被丢掉。
    const onMove = (ev: PointerEvent) => {
      pointerPos.current = { x: ev.clientX, y: ev.clientY };
      const cur = pressRef.current;
      if (!cur) return;
      if (dragIdRef.current === null) {
        const moved =
          Math.abs(ev.clientX - cur.startX) + Math.abs(ev.clientY - cur.startY);
        if (moved < MOVE_THRESHOLD_PX) return;
        // 移动超阈值 → 立刻进入拖拽态（不用等长按）
        clearLongPress();
        dragIdRef.current = cur.id;
        setDragId(cur.id);
      }
      setDropTarget(hitTest(ev.clientX, ev.clientY, dragIdRef.current));
    };

    const teardown = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      teardownRef.current = null;
    };

    function onUp() {
      clearLongPress();
      teardown();
      pressRef.current = null;
      const dragging = dragIdRef.current;
      dragIdRef.current = null;
      setDragId(null);
      setDropTarget(null);
      if (dragging === null) return;

      // 松手位置再算一次落点（比 move 里的更准）
      const target = hitTest(
        pointerPos.current.x,
        pointerPos.current.y,
        dragging,
      );
      if (!target) return;
      lastDragEndAt.current = Date.now();
      void commitReorder(dragging, target.id, target.after);
    }

    teardownRef.current = teardown;
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    // 长按到点 → 进入拖拽态
    longPressTimer.current = window.setTimeout(() => {
      if (!pressRef.current) return;
      dragIdRef.current = pressRef.current.id;
      setDragId(pressRef.current.id);
    }, LONG_PRESS_MS);
  }

  /** 提交新顺序。 */
  async function commitReorder(
    draggedId: number,
    hoveredId: number,
    placeAfter: boolean,
  ) {
    try {
      // ⚠️ 用**全量**列表算新顺序：带筛选时只把可见子集发上去，
      // 会把隐藏条目的 sort_order 冲掉，顺序就乱了。
      const all = await inspirationsApi.list({ limit: GLOBAL_LIST_LIMIT });
      const globalIds = all.map((i) => i.id);
      const pinnedMap = new Map(all.map((i) => [i.id, i.pinned] as const));
      const isPinned = (id: number) => pinnedMap.get(id) === true;
      const newIds = computeReorderedIds(
        globalIds,
        isPinned,
        draggedId,
        hoveredId,
        placeAfter,
      );
      if (!newIds) return;
      await inspirationsApi.reorder(newIds);
      await load();
      toast.success("顺序已保存");
    } catch (e: unknown) {
      toast.error("排序保存失败", { description: errText(e) });
    }
  }

  const menuInspiration = menu
    ? items.find((i) => i.id === menu.id) ?? null
    : null;

  return (
    <div className="space-y-3">
      {/* 标题栏：类型筛选 + 管理按钮 */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-neutral-500">类型筛选</span>
        <Select
          value={typeFilter ?? "all"}
          onValueChange={(v) => onTypeFilterChange(v === "all" ? null : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="keyword">关键词</SelectItem>
            <SelectItem value="plot">剧情</SelectItem>
            <SelectItem value="snippet">片段</SelectItem>
            <SelectItem value="image">画面</SelectItem>
            <SelectItem value="note">备注</SelectItem>
          </SelectContent>
        </Select>

        {!manageMode ? (
          <Button size="sm" variant="outline" onClick={toggleManageMode}>
            <ListChecks className="mr-1.5 h-3.5 w-3.5" />
            管理
          </Button>
        ) : null}

        <span className="ml-auto text-xs text-neutral-500">
          共 {items.length} 条
        </span>
      </div>

      {loading && <LoadingSkeleton rows={4} height={80} />}
      {error && !loading && <ErrorState message={error} />}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          icon="💡"
          title="还没有灵感"
          description="去灵感园保存关键词 / 剧情 / 片段 / 画面 / 备注"
        />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="space-y-2">
          {items.map((ins) => (
            <InspirationCard
              key={ins.id}
              ins={ins}
              novelName={
                ins.novel_id !== null
                  ? (novelNameById.get(ins.novel_id) ??
                    `novel #${ins.novel_id}`)
                  : null
              }
              manageMode={manageMode}
              selected={selected.has(ins.id)}
              dragging={dragId === ins.id}
              indicatorVisible={dropTarget?.id === ins.id}
              indicatorBefore={dropTarget?.id === ins.id && !dropTarget.after}
              onOpen={handleOpen}
              onDelete={askDelete}
              onToggleSelect={handleToggleSelect}
              onPointerDown={handleCardPointerDown}
              onContextMenu={handleContextMenu}
            />
          ))}
        </div>
      )}

      {/* 管理模式底部操作条 */}
      {manageMode ? (
        <div className="sticky bottom-0 flex items-center gap-2 rounded-lg border border-neutral-200 bg-white/95 px-3 py-2 shadow-sm backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/95">
          <span className="text-[12.5px] text-neutral-600 dark:text-neutral-300">
            已选 {selected.size} 项
          </span>
          <Button
            size="sm"
            variant="destructive"
            disabled={selected.size === 0}
            onClick={askBatchDelete}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            批量删除
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            onClick={toggleManageMode}
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            退出管理
          </Button>
        </div>
      ) : null}

      <InspirationContextMenu
        state={menu}
        pinned={menuInspiration?.pinned ?? false}
        onClose={() => setMenu(null)}
        onRename={(id) => {
          const ins = items.find((i) => i.id === id);
          if (ins) openRename(ins);
        }}
        onDelete={(id) => {
          const ins = items.find((i) => i.id === id);
          if (ins) askDelete(ins);
        }}
        onTogglePin={(id) => {
          const ins = items.find((i) => i.id === id);
          if (ins) void handleTogglePin(ins);
        }}
      />

      <InspirationRenameDialog
        open={renameTarget !== null}
        initialTitle={renameTarget?.title ?? ""}
        onSubmit={(title) => void commitRename(title)}
      />

      <InspirationConfirmDialog
        open={confirm !== null}
        title={confirm && confirm.ids.length > 1 ? "批量删除素材" : "删除素材"}
        description={
          confirm && confirm.ids.length > 1
            ? `将删除 ${confirm.ids.length} 条素材，此操作不可恢复。`
            : "此操作不可恢复。"
        }
        confirmLabel={confirm && confirm.ids.length > 1 ? "批量删除" : "删除"}
        onConfirm={() => void commitDelete()}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
