/**
 * 编辑区外观偏好：纸面模式 + 正文字号。
 *
 * 为什么单独一个 store：
 * 这两项是**纯本地**偏好（不上后端），但必须在**应用启动时就生效**。
 * 之前它们只存在设置页组件的 useState 里 —— 组件卸载就丢，
 * 会出现"重启后界面显示'跟随主题'、实际 DOM 上却没有那个 class"的割裂。
 *
 * 这里把状态交给 zustand persist（localStorage），
 * 再由 AppShell 统一把值应用到 DOM（class / CSS 变量），职责单一。
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

/** 编辑区配色：固定浅色纸面 / 跟随主题 */
export type PaperMode = "paper" | "follow";

interface AppearanceState {
  paperMode: PaperMode;
  fontSize: number;
  setPaperMode: (m: PaperMode) => void;
  setFontSize: (n: number) => void;
}

/** 字号合法区间（与设置页滑块一致） */
export const FONT_SIZE_MIN = 13;
export const FONT_SIZE_MAX = 22;

/** 默认正文字号（px） */
export const DEFAULT_FONT_SIZE = 16.5;

/**
 * 创建外观偏好 store。
 *
 * @param storage 可选的持久化后端。生产环境不传（默认用浏览器 localStorage）；
 *   测试里传入内存实现 —— zustand persist 的默认 storage 引用的是裸全局
 *   `localStorage`，在 node 环境下不可访问。
 */
export function createAppearanceStore(storage?: StateStorage) {
  return create<AppearanceState>()(
    persist(
      (set) => ({
        paperMode: "paper",
        fontSize: DEFAULT_FONT_SIZE,
        setPaperMode: (paperMode) => set({ paperMode }),
        setFontSize: (fontSize) => set({ fontSize }),
      }),
      {
        name: "book-soul-appearance",
        partialize: (s) => ({
          paperMode: s.paperMode,
          fontSize: s.fontSize,
        }),
        ...(storage ? { storage: createJSONStorage(() => storage) } : {}),
      },
    ),
  );
}

/** 全局单例（应用里统一用这个）。 */
export const useAppearanceStore = createAppearanceStore();
