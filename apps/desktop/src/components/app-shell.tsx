/**
 * 应用外壳：52px 顶栏 + 56px 图标栏 + 内容区。
 *
 * 重设计要点（对比旧的 Layout.tsx）：
 * - 导航从 6 项平铺收敛为 5 项：写作 / 开新书 / 聊天 / 素材库 / 设置
 *   （2026-10-25 新增「聊天」：与模型探讨想法 + 项目管理）
 * - 顶栏承担**全局上下文**：作品切换器（全局唯一）+ 面包屑 + 模型状态灯
 * - 作品切换写入 workspaceStore 并持久化，跨页、跨启动都保持
 */

import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Moon,
  PenLine,
  Library,
  MessagesSquare,
  Settings,
  Sparkles,
  Sun,
} from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { useUIStore } from "@/stores/uiStore";
import { useAppearanceStore } from "@/stores/appearance-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { settingsApi } from "@/api/settings";
import NovelSwitcher from "@/components/novel-switcher";
import ModelStatusPill from "@/components/model-status-pill";
import { cn } from "@/lib/utils";

interface RailItem {
  to: string;
  label: string;
  icon: typeof PenLine;
  end?: boolean;
}

/** 图标栏 5 项（顺序即使用频率） */
const RAIL_ITEMS: RailItem[] = [
  { to: "/", label: "写作", icon: PenLine, end: true },
  { to: "/new", label: "开新书", icon: Sparkles },
  { to: "/chat", label: "聊天", icon: MessagesSquare },
  { to: "/library", label: "素材库", icon: Library },
  { to: "/settings", label: "设置", icon: Settings },
];

export default function AppShell() {
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);
  const chapterLabel = useWorkspaceStore((s) => s.chapterLabel);
  const paperMode = useAppearanceStore((s) => s.paperMode);
  const fontSize = useAppearanceStore((s) => s.fontSize);

  // 主题 → <html class="dark">
  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  // 编辑区：纸面模式 / 跟随主题
  useEffect(() => {
    document.documentElement.classList.toggle(
      "paper-follow-theme",
      paperMode === "follow",
    );
  }, [paperMode]);

  // 编辑区：正文字号（CSS 变量）
  useEffect(() => {
    document.documentElement.style.setProperty(
      "--novel-font-size",
      `${fontSize}px`,
    );
  }, [fontSize]);

  // 启动时从后端读主题 —— 后端是权威来源（设置页「保存」写的就是它）。
  // 读不到就保留 localStorage 里的偏好，别把用户打回默认深色。
  useEffect(() => {
    let cancelled = false;
    settingsApi
      .get()
      .then((s) => {
        if (cancelled) return;
        if (s?.ui?.theme) setTheme(s.ui.theme);
      })
      .catch(() => {
        // 后端不可达：沿用本地偏好
      });
    return () => {
      cancelled = true;
    };
  }, [setTheme]);

  /** 顶栏切换主题：立即生效 + 顺手落盘（否则重启就丢） */
  const handleToggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    void settingsApi
      .update({ ui: { theme: next } })
      .catch(() => undefined);
  };

  return (
    <div className="flex h-screen flex-col bg-neutral-50 text-neutral-900 antialiased dark:bg-neutral-950 dark:text-neutral-100">
      {/* ===== 顶栏：全局上下文 ===== */}
      <header className="flex h-[52px] shrink-0 items-center gap-3.5 border-b border-neutral-200 bg-white px-3.5 dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex items-center gap-2">
          <span
            className="h-1.5 w-1.5 rounded-full bg-indigo-500"
            aria-hidden
          />
          <span className="text-[13.5px] font-semibold tracking-tight">Book Soul</span>
        </div>

        <NovelSwitcher />

        {chapterLabel ? (
          <div className="flex min-w-0 items-center gap-1.5 text-[12.5px] text-neutral-500 dark:text-neutral-400">
            <span className="text-neutral-300 dark:text-neutral-600">›</span>
            <span className="truncate">{chapterLabel}</span>
          </div>
        ) : null}

        <div className="flex-1" />

        <ModelStatusPill />

        <button
          type="button"
          onClick={handleToggleTheme}
          title={theme === "dark" ? "切换到浅色" : "切换到深色"}
          aria-label="切换主题"
          className="grid h-[30px] w-[30px] place-items-center rounded-lg text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
        >
          {theme === "dark" ? (
            <Moon className="h-[15px] w-[15px]" />
          ) : (
            <Sun className="h-[15px] w-[15px]" />
          )}
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* ===== 56px 图标栏 ===== */}
        <nav className="flex w-14 shrink-0 flex-col items-center gap-0.5 border-r border-neutral-200 bg-white py-2.5 dark:border-neutral-800 dark:bg-neutral-900">
          {RAIL_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={item.label}
              className={({ isActive }) =>
                cn(
                  "flex w-10 flex-col items-center gap-0.5 rounded-[10px] border border-transparent py-1.5 text-[9.5px] transition-colors",
                  isActive
                    ? "border-indigo-500/40 bg-indigo-500/10 font-medium text-indigo-600 dark:text-indigo-300"
                    : "text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 dark:text-neutral-500 dark:hover:bg-neutral-800 dark:hover:text-neutral-200",
                )
              }
            >
              <item.icon className="h-[17px] w-[17px]" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* ===== 内容区 ===== */}
        <main className="min-w-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>

      <Toaster position="bottom-right" theme="dark" richColors closeButton />
    </div>
  );
}
