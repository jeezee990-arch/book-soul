/**
 * 作品卡右键菜单（2026-10-30）。
 *
 * 与素材库（灵感）的右键菜单同一套实现思路：
 * 不用 shadcn `DropdownMenu`（它要 `DropdownMenuTrigger` 做锚点，
 * 右键菜单要贴着**鼠标位置**弹，触发点是随机的），
 * 自己实现一个绝对定位菜单 —— 依赖为零、行为更可控。
 *
 * 交互约定：
 * - 点外面 / 按 Esc / 窗口失焦 → 关闭
 * - 菜单项点击 `preventDefault()` + `stopPropagation()`（别把事件冒到卡片上）
 * - 边界项（已经在最上/最下）显示但置灰
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  FileDown,
  PenLine,
  Pencil,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";

/** 右键菜单状态。 */
export interface NovelMenuState {
  /** 触发右键的作品 id。 */
  id: number;
  /** 鼠标位置（视口坐标）。 */
  x: number;
  /** 鼠标位置（视口坐标）。 */
  y: number;
}

interface Props {
  /** 当前菜单状态；null 表示不显示。 */
  state: NovelMenuState | null;
  /** 目标作品是否已经是第一本（决定「上移」是否置灰）。 */
  atTop: boolean;
  /** 目标作品是否已经是最后一本（决定「下移」是否置灰）。 */
  atBottom: boolean;
  /** 关闭菜单。 */
  onClose: () => void;
  /** 继续写（切到写作页）。 */
  onContinue: (id: number) => void;
  /** 重命名。 */
  onRename: (id: number) => void;
  /** 上移一位。 */
  onMoveUp: (id: number) => void;
  /** 下移一位。 */
  onMoveDown: (id: number) => void;
  /** 导出。 */
  onExport: (id: number, format: "md" | "html" | "docx") => void;
  /** 删除。 */
  onDelete: (id: number) => void;
}

/** 菜单项的统一样式。 */
const ITEM_CLASS =
  "flex w-full cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[12.5px] text-neutral-700 transition-colors hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-800";

/** 置灰项的样式。 */
const DISABLED_CLASS = "pointer-events-none opacity-40";

/**
 * 作品卡右键菜单。
 *
 * @param props - 组件属性
 */
export default function NovelContextMenu({
  state,
  atTop,
  atBottom,
  onClose,
  onContinue,
  onRename,
  onMoveUp,
  onMoveDown,
  onExport,
  onDelete,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  // 打开时贴到鼠标位置，再夹到视口内（贴着右下角时菜单会跑出屏幕）
  useLayoutEffect(() => {
    if (!state) return;
    const el = ref.current;
    const width = el?.offsetWidth ?? 170;
    const height = el?.offsetHeight ?? 260;
    const maxX = window.innerWidth - width - 8;
    const maxY = window.innerHeight - height - 8;
    setPos({
      x: Math.max(8, Math.min(state.x, maxX)),
      y: Math.max(8, Math.min(state.y, maxY)),
    });
  }, [state]);

  // 点外面 / 按 Esc / 窗口失焦 → 关闭
  useEffect(() => {
    if (!state) return;
    function onPointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("blur", onClose);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("blur", onClose);
    };
  }, [state, onClose]);

  if (!state) return null;

  /** 统一的菜单项点击处理：屏蔽冒泡 + 执行回调 + 关闭菜单。 */
  function run(fn: () => void) {
    return (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      fn();
      onClose();
    };
  }

  return (
    <div
      ref={ref}
      role="menu"
      className="fixed z-50 min-w-[10.5rem] rounded-lg border border-neutral-200 bg-white py-1 shadow-lg dark:border-neutral-800 dark:bg-neutral-900"
      style={{ left: pos.x, top: pos.y }}
      onContextMenu={(e) => e.preventDefault()}
    >
      <button
        type="button"
        role="menuitem"
        className={ITEM_CLASS}
        onClick={run(() => onContinue(state.id))}
      >
        <PenLine className="h-3.5 w-3.5 text-neutral-400" />
        继续写
      </button>
      <button
        type="button"
        role="menuitem"
        className={ITEM_CLASS}
        onClick={run(() => onRename(state.id))}
      >
        <Pencil className="h-3.5 w-3.5 text-neutral-400" />
        重命名
      </button>

      <div className="my-1 h-px bg-neutral-200 dark:bg-neutral-800" />

      <button
        type="button"
        role="menuitem"
        className={cn(ITEM_CLASS, atTop && DISABLED_CLASS)}
        onClick={run(() => onMoveUp(state.id))}
      >
        <ArrowUp className="h-3.5 w-3.5 text-neutral-400" />
        上移
      </button>
      <button
        type="button"
        role="menuitem"
        className={cn(ITEM_CLASS, atBottom && DISABLED_CLASS)}
        onClick={run(() => onMoveDown(state.id))}
      >
        <ArrowDown className="h-3.5 w-3.5 text-neutral-400" />
        下移
      </button>

      <div className="my-1 h-px bg-neutral-200 dark:bg-neutral-800" />

      <button
        type="button"
        role="menuitem"
        className={ITEM_CLASS}
        onClick={run(() => onExport(state.id, "md"))}
      >
        <FileDown className="h-3.5 w-3.5 text-neutral-400" />
        导出 Markdown
      </button>
      <button
        type="button"
        role="menuitem"
        className={ITEM_CLASS}
        onClick={run(() => onExport(state.id, "html"))}
      >
        <FileDown className="h-3.5 w-3.5 text-neutral-400" />
        导出 HTML
      </button>
      <button
        type="button"
        role="menuitem"
        className={ITEM_CLASS}
        onClick={run(() => onExport(state.id, "docx"))}
      >
        <FileDown className="h-3.5 w-3.5 text-neutral-400" />
        导出 Word
      </button>

      <div className="my-1 h-px bg-neutral-200 dark:bg-neutral-800" />

      <button
        type="button"
        role="menuitem"
        className={cn(
          ITEM_CLASS,
          "text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40",
        )}
        onClick={run(() => onDelete(state.id))}
      >
        <Trash2 className="h-3.5 w-3.5" />
        删除
      </button>
    </div>
  );
}
