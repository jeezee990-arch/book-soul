/**
 * 全局 UI 状态：侧栏折叠 / 主题 / 全局 loading。
 *
 * 主题：dark / light。setTheme 会同步操作 <html class="dark">，
 * 这样 css 变量（shadcn tokens）立即生效。
 */

import { create } from "zustand";

export type Theme = "dark" | "light";

interface UIState {
  sidebarCollapsed: boolean;
  theme: Theme;
  globalLoading: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  setTheme: (t: Theme) => void;
  setLoading: (l: boolean) => void;
}

function applyThemeClass(t: Theme) {
  if (t === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  theme: "dark",
  globalLoading: false,
  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  setTheme: (t) => {
    applyThemeClass(t);
    set({ theme: t });
  },
  setLoading: (l) => set({ globalLoading: l }),
}));
