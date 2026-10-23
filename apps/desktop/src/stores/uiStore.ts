/**
 * 全局 UI 状态：侧栏折叠 / 主题 / 全局 loading。
 *
 * 主题：dark / light。setTheme 会同步操作 <html class="dark">，
 * 这样 css 变量（shadcn tokens）立即生效。
 *
 * 持久化：主题写进 localStorage，**同时**后端 `GET /settings` 也是权威来源
 * （设置页「保存」写的是后端）。AppShell 启动时会读后端覆盖本地值 ——
 * 这样换数据目录 / 换机器时主题也跟着设置走。
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

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

/** 把主题写进 <html class="dark">，shadcn tokens 立即生效。 */
export function applyThemeClass(t: Theme) {
  // node 环境（单测）没有 document，跳过即可
  if (typeof document === "undefined") return;
  if (t === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

/**
 * 创建 UI store。
 *
 * @param storage 可选的持久化后端；测试用内存实现（node 环境没有 localStorage）。
 */
export function createUIStore(storage?: StateStorage) {
  return create<UIState>()(
    persist(
      (set) => ({
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
      }),
      {
        name: "book-soul-ui",
        partialize: (s) => ({ theme: s.theme }),
        ...(storage ? { storage: createJSONStorage(() => storage) } : {}),
      },
    ),
  );
}

/** 全局单例（应用里统一用这个）。 */
export const useUIStore = createUIStore();
