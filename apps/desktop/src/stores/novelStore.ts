/**
 * 当前选中的作品 / 章节 / 人物 状态。
 *
 * 注意：store 只管状态 + setter，**不**做 API 调用。
 * 数据获取由 page 层用 useEffect + 调用 API client，然后把结果 setState 到 store。
 * 这样 store 保持纯净、易测、易持久化（未来 phase 加 localStorage 持久）。
 */

import { create } from "zustand";
import type { Novel, Chapter, Character } from "@/lib/types";

interface NovelState {
  currentNovel: Novel | null;
  currentChapter: Chapter | null;
  currentCharacter: Character | null;
  setNovel: (n: Novel | null) => void;
  setChapter: (c: Chapter | null) => void;
  setCharacter: (c: Character | null) => void;
  /** 切换作品时清掉章节/人物（避免数据错位） */
  clearOnNovelChange: () => void;
  clear: () => void;
}

export const useNovelStore = create<NovelState>((set) => ({
  currentNovel: null,
  currentChapter: null,
  currentCharacter: null,
  setNovel: (n) => set({ currentNovel: n }),
  setChapter: (c) => set({ currentChapter: c }),
  setCharacter: (c) => set({ currentCharacter: c }),
  clearOnNovelChange: () => set({ currentChapter: null, currentCharacter: null }),
  clear: () =>
    set({
      currentNovel: null,
      currentChapter: null,
      currentCharacter: null,
    }),
}));
