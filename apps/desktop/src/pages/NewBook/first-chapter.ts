/**
 * 从大纲结构里取第一章（标题 + 概要）。
 *
 * 独立成文件的原因：这是**纯函数**（无 React / 无 IO），
 * 可以直接单测；混在页面文件里就只能靠 UI 测试间接覆盖。
 */

/** 大纲里的一个章节（结构化视图）。 */
interface OutlineChapter {
  title?: string;
  summary?: string | null;
  key_events?: string[];
}

/** 大纲里的一卷。 */
interface OutlineVolume {
  chapters?: OutlineChapter[];
}

/** 取到的第一章信息。 */
export interface FirstChapter {
  /** 章节标题。 */
  title: string;
  /** 章节概要（可为空）。 */
  outline: string | null;
}

/**
 * 从大纲结构里取第一章（标题 + 概要），取不到返回 null。
 *
 * 兼容两种大纲结构：
 * - `volumes[].chapters[]`（两阶段大纲的正式格式）
 * - `chapters[]`（单层旧格式）
 *
 * @param structure 大纲结构（任意 JSON 对象）
 * @returns 第一章信息，取不到返回 null
 */
export function firstChapterOf(
  structure: Record<string, unknown>,
): FirstChapter | null {
  const volumes = (structure.volumes ?? []) as OutlineVolume[];
  for (const v of volumes) {
    const c = v.chapters?.[0];
    if (c) return toFirstChapter(c);
  }
  const flat = (structure.chapters ?? []) as OutlineChapter[];
  const first = flat[0];
  if (first) return toFirstChapter(first);
  return null;
}

/**
 * 把一个章节条目转成"标题 + 概要"。
 *
 * @param c 章节条目
 * @returns 第一章信息
 */
function toFirstChapter(c: OutlineChapter): FirstChapter {
  const outline = [
    c.summary,
    ...(c.key_events ?? []).map((e) => `· ${e}`),
  ]
    .filter(Boolean)
    .join("\n");
  return { title: c.title ?? "第一章", outline: outline || null };
}
