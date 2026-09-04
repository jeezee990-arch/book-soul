/**
 * Settings 缓存（避免每个 page 各自 fetch /settings）。
 *
 * 用法：
 * - App 启动时（main.tsx）调一次 settingsApi.get() → setSettings
 * - page 读 useSettingsStore((s) => s.settings)
 * - 改 settings 后（saveApiKey / update）调 setSettings 刷新
 *
 * 注意：store 不做 fetch，只缓存 page 拿到的数据。
 */

import { create } from "zustand";
import type { Settings } from "@/api/settings";

interface SettingsState {
  settings: Settings | null;
  loaded: boolean;
  setSettings: (s: Settings) => void;
  clear: () => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  loaded: false,
  setSettings: (s) => set({ settings: s, loaded: true }),
  clear: () => set({ settings: null, loaded: false }),
}));
