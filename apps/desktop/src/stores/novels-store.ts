/**
 * 作品列表缓存（全局共享）。
 *
 * 为什么要缓存：顶栏的作品切换器、写作页、素材库都需要作品列表。
 * 没有 react-query，三处各拉一次就是三次重复请求。
 *
 * 这里用 Zustand 做一次性缓存：谁先调 load() 谁拉，其余直接读缓存；
 * 新建/删除作品后调 refresh() 强制重拉。
 */

import { create } from "zustand";
import { novelsApi } from "@/api/novels";
import { ApiError } from "@/api";
import type { Novel } from "@/lib/types";

interface NovelsState {
  novels: Novel[];
  loading: boolean;
  error: string | null;
  /** 是否已经拉过（避免重复请求） */
  loaded: boolean;
  /**
   * 是否有一次强制刷新被"排队"了。
   *
   * ⚠️ 2026-10-25 巡检：原来 `load()` 开头 `if (s.loading) return;`，
   *    飞行中的请求会把紧接着的 `refresh()` 静默吞掉 →
   *    开新书写完，顶栏作品列表少一本（要用户手动再触发一次才出现）。
   *    现在：飞行中收到 force 请求 → 记一个 needsRefresh，落地后再补拉一次。
   */
  needsRefresh: boolean;
  load: (force?: boolean) => Promise<void>;
  refresh: () => Promise<void>;
}

export const useNovelsStore = create<NovelsState>((set, get) => ({
  novels: [],
  loading: false,
  error: null,
  loaded: false,
  needsRefresh: false,

  load: async (force = false) => {
    const s = get();
    if (s.loading) {
      // 正在拉 → 记住"落地后要再拉一次"
      if (force) set({ needsRefresh: true });
      return;
    }
    if (s.loaded && !force) return;

    set({ loading: true, error: null });
    try {
      const novels = await novelsApi.list();
      set({ novels, loading: false, loaded: true, error: null });
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      set({ loading: false, loaded: true, error: msg });
    } finally {
      if (get().needsRefresh) {
        set({ needsRefresh: false });
        void get().load(true);
      }
    }
  },

  refresh: async () => {
    set({ loaded: false });
    await get().load(true);
  },
}));
