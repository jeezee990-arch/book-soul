/**
 * 全局工作区状态：当前作品 + 当前章节。
 *
 * 为什么要有这个 store：
 * 现状里"选作品"在创作页、人物卡页各写了一份下拉框，切换页面就丢；
 * 用户在 A 书写作、跳去另一个页面，会默认选中列表里的第一本书（可能不是他要的）。
 *
 * 这里把"当前作品"提升为**全局唯一真相**，顶栏切换一次全站生效，
 * 并持久化到 localStorage —— 重开应用直接回到上次写的那一章。
 *
 * store 只管状态，不做 API 调用（数据获取在页面层）。
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";

interface WorkspaceState {
  /** 当前作品 id（null = 未选择） */
  novelId: number | null;
  /** 当前章节 id（null = 未选择） */
  chapterId: number | null;
  /** 当前章节的展示名（顶栏面包屑用；存下来避免顶栏重复拉章节列表） */
  chapterLabel: string | null;
  /** 切换作品 */
  setNovelId: (id: number | null) => void;
  /** 切换章节 */
  setChapterId: (id: number | null, label?: string | null) => void;
  /** 同时设置作品 + 章节（开新书完成后一次性落位用） */
  setTarget: (
    novelId: number,
    chapterId?: number | null,
    chapterLabel?: string | null,
  ) => void;
  /** 全部清空 */
  reset: () => void;
}

const STORAGE_KEY = "book-soul-workspace";

/**
 * 创建工作区 store。
 *
 * @param storage 可选的持久化后端。生产环境不传（默认用浏览器 localStorage）；
 *   测试里传入内存实现 —— zustand persist 的默认 storage 引用的是裸全局
 *   `localStorage`，在 node 环境下不可访问，会报 "storage is currently unavailable"。
 */
export function createWorkspaceStore(storage?: StateStorage) {
  return create<WorkspaceState>()(
    persist(
      (set) => ({
        novelId: null,
        chapterId: null,
        chapterLabel: null,
        setNovelId: (id) =>
          set((s) => ({
            novelId: id,
            // 换作品必然换章节，避免章节 id 串到另一本书
            chapterId: s.novelId === id ? s.chapterId : null,
            chapterLabel: s.novelId === id ? s.chapterLabel : null,
          })),
        setChapterId: (id, label = null) =>
          set({ chapterId: id, chapterLabel: label }),
        setTarget: (novelId, chapterId = null, chapterLabel = null) =>
          set({ novelId, chapterId, chapterLabel }),
        reset: () => set({ novelId: null, chapterId: null, chapterLabel: null }),
      }),
      {
        name: STORAGE_KEY,
        partialize: (s) => ({
          novelId: s.novelId,
          chapterId: s.chapterId,
          chapterLabel: s.chapterLabel,
        }),
        ...(storage
          ? { storage: createJSONStorage(() => storage) }
          : {}),
      },
    ),
  );
}

/** 全局单例（应用里统一用这个）。 */
export const useWorkspaceStore = createWorkspaceStore();

export { STORAGE_KEY as WORKSPACE_STORAGE_KEY };
