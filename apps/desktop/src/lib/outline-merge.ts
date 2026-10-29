/**
 * 大纲结构的前端合并工具（2026-10-25 新增，两阶段大纲）。
 *
 * 两阶段大纲的流式事件顺序：
 * 1. ``partial``  —— 骨架阶段的增量结构（卷 + 章标题）
 * 2. ``skeleton`` —— 骨架完成（全书卷章结构齐了）
 * 3. ``volume_done`` —— 某一卷的细节补齐（概要 + 关键事件），**按下标替换**
 *
 * 前端要把这些事件合成一份"当前最完整的结构"给 UI 渲染，
 * 合并逻辑必须与后端 `merge_volume_details` 保持一致。
 *
 * ⚠️ 2026-10-29（需求7）：后端保证**每一章都有概要** ——
 * 失败卷也会补「【待细化】」占位（不是只有标题）。
 * 前端流式阶段要一致，所以某卷报 ``volume_error`` 时也要补占位，
 * 否则用户会看到"一堆只有标题的空章节"。
 */

/** 大纲结构（宽松类型：具体形状由 outline_type 决定）。 */
export type OutlineStructure = Record<string, unknown>;

/** 取结构里的卷数组（没有就返回空数组）。 */
function getVolumes(structure: OutlineStructure | null): OutlineStructure[] {
  if (!structure) return [];
  const volumes = structure.volumes;
  return Array.isArray(volumes) ? (volumes as OutlineStructure[]) : [];
}

/** 章标题（兜底用）。 */
function chapterTitle(chapter: OutlineStructure): string {
  const title = chapter.title;
  return typeof title === "string" && title.trim() ? title.trim() : "本章";
}

/**
 * 给"没补上细节"的章节补占位概要（与后端 `merge_volume_details` 一致）。
 *
 * @param structure 当前结构
 * @param index 卷下标
 * @returns 合并后的新结构（**不修改**入参）
 */
export function fillPendingChapters(
  structure: OutlineStructure | null,
  index: number,
): OutlineStructure {
  const volumes = [...getVolumes(structure)];
  const base = volumes[index];
  if (!base) return structure ?? {};

  const volumeName = typeof base.name === "string" ? base.name : "";
  const volumeSummary = typeof base.summary === "string" ? base.summary : "";
  const context = volumeSummary || (volumeName ? `属于《${volumeName}》` : "");

  const baseChapters = Array.isArray(base.chapters)
    ? (base.chapters as OutlineStructure[])
    : [];
  const chapters = baseChapters.map((chapter) => {
    const merged: OutlineStructure = { ...chapter };
    const summary = merged.summary;
    const hasSummary = typeof summary === "string" && summary.trim() !== "";
    if (!hasSummary) {
      const title = chapterTitle(chapter);
      const tail = context ? `${context}。` : "";
      merged.summary = `【待细化】${title} —— ${tail}本章概要尚未生成，可重新生成该卷。`;
    }
    if (!Array.isArray(merged.key_events)) merged.key_events = [];
    return merged;
  });

  volumes[index] = { ...base, chapters };
  return { ...(structure ?? {}), volumes };
}

/**
 * 把某一卷的细节合并进结构（下标对应）。
 *
 * @param structure 当前结构
 * @param index 卷下标
 * @param volume 后端补好的那一卷
 * @returns 合并后的新结构（**不修改**入参）
 */
export function mergeVolumeIntoStructure(
  structure: OutlineStructure | null,
  index: number,
  volume: OutlineStructure,
): OutlineStructure {
  const volumes = [...getVolumes(structure)];
  const base = volumes[index];
  if (!base) return structure ?? {};

  const baseChapters = Array.isArray(base.chapters)
    ? (base.chapters as OutlineStructure[])
    : [];
  const detailChapters = Array.isArray(volume.chapters)
    ? (volume.chapters as OutlineStructure[])
    : [];

  const chapters = baseChapters.map((chapter, i) => {
    const extra = detailChapters[i];
    const merged: OutlineStructure = { ...chapter };
    if (extra) {
      const summary = extra.summary;
      if (typeof summary === "string" && summary.trim()) {
        merged.summary = summary.trim();
      }
      const events = extra.key_events;
      if (Array.isArray(events) && events.length > 0) {
        merged.key_events = events.filter(
          (e): e is string => typeof e === "string" && e.trim() !== "",
        );
      }
    }
    if (!Array.isArray(merged.key_events)) merged.key_events = [];
    return merged;
  });

  const newVolume: OutlineStructure = { ...base, chapters };
  if (typeof volume.summary === "string" && volume.summary.trim()) {
    newVolume.summary = volume.summary;
  }
  volumes[index] = newVolume;
  return { ...(structure ?? {}), volumes };
}
