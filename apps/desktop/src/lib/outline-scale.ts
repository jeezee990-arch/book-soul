/**
 * 大纲规模参数（2026-10-25 新增）。
 *
 * 为什么需要
 * ----------
 * 旧的大纲 prompt 把规模写死成"3-5 卷、每卷 6-10 章、总 20-40 章"。
 * 作者在想法里写"全书 100 章、每章 3000 字"，模型只能二选一 ——
 * 多数情况下按 prompt 走，作者的要求被**静默丢弃**
 * （用户实测："添加想法录入后大纲生成部分未按照要求进行生成"）。
 *
 * 现在规模是**显式参数**，前端解析出来传给后端，后端写进 prompt 的硬性要求。
 *
 * 本模块与后端 `server/src/core/outline_scale.py` 行为一致
 * （前端负责"识别 + 显示"，后端负责"强制执行"）。
 */

/** 大纲规模三元组。 */
export interface OutlineScale {
  /** 全书总章数 */
  totalChapters: number;
  /** 每卷章数（目标值） */
  chaptersPerVolume: number;
  /** 每章字数 */
  wordsPerChapter: number;
}

/** 默认规模。 */
export const DEFAULT_OUTLINE_SCALE: OutlineScale = {
  totalChapters: 30,
  chaptersPerVolume: 10,
  wordsPerChapter: 3000,
};

export const MIN_TOTAL_CHAPTERS = 1;
export const MAX_TOTAL_CHAPTERS = 500;
export const MIN_CHAPTERS_PER_VOLUME = 1;
export const MAX_CHAPTERS_PER_VOLUME = 100;
export const MIN_WORDS_PER_CHAPTER = 500;
export const MAX_WORDS_PER_CHAPTER = 20000;

/** 把任意值夹到区间内。 */
function clamp(value: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, value));
}

/** 把规模规整成合法值（缺省填默认、越界裁剪）。 */
export function normalizeScale(
  scale?: Partial<OutlineScale> | null,
): OutlineScale {
  const total = clamp(
    Math.round(scale?.totalChapters ?? DEFAULT_OUTLINE_SCALE.totalChapters),
    MIN_TOTAL_CHAPTERS,
    MAX_TOTAL_CHAPTERS,
  );
  const cpv = clamp(
    Math.round(
      scale?.chaptersPerVolume ?? DEFAULT_OUTLINE_SCALE.chaptersPerVolume,
    ),
    MIN_CHAPTERS_PER_VOLUME,
    MAX_CHAPTERS_PER_VOLUME,
  );
  const wpc = clamp(
    Math.round(scale?.wordsPerChapter ?? DEFAULT_OUTLINE_SCALE.wordsPerChapter),
    MIN_WORDS_PER_CHAPTER,
    MAX_WORDS_PER_CHAPTER,
  );
  return {
    totalChapters: total,
    chaptersPerVolume: Math.min(cpv, total),
    wordsPerChapter: wpc,
  };
}

/** 总卷数（向上取整）。 */
export function scaleVolumeCount(scale: OutlineScale): number {
  const cpv = Math.max(1, scale.chaptersPerVolume);
  return Math.max(1, Math.ceil(scale.totalChapters / cpv));
}

/** 全书预计总字数。 */
export function scaleTotalWords(scale: OutlineScale): number {
  return scale.totalChapters * scale.wordsPerChapter;
}

/** 总字数的中文可读形式（"30.5 万字"）。 */
export function formatTotalWords(words: number): string {
  if (words >= 10000) {
    const w = words / 10000;
    return `${Number.isInteger(w) ? w : w.toFixed(1)} 万字`;
  }
  return `${words} 字`;
}

// ===== 自然语言解析 =====

const CN_DIGITS: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
};
const CN_UNITS: Record<string, number> = { 十: 10, 百: 100, 千: 1000, 万: 10000 };

/** 中文数字转整数（"一百二十三"→123）；解析不了返回 null。 */
export function cnToInt(text: string): number | null {
  if (!text) return null;
  for (const ch of text) {
    if (!(ch in CN_DIGITS) && !(ch in CN_UNITS)) return null;
  }
  let total = 0;
  let section = 0;
  let number = 0;
  for (const ch of text) {
    if (ch in CN_DIGITS) {
      number = CN_DIGITS[ch];
    } else {
      const unit = CN_UNITS[ch];
      if (unit === 10000) {
        section = (section + number) * unit;
        total += section;
        section = 0;
      } else {
        if (number === 0) number = 1; // "十五" → 15
        section += number * unit;
      }
      number = 0;
    }
  }
  return total + section + number;
}

const NUM = "(?:\\d+(?:\\.\\d+)?|[零〇一二两三四五六七八九十百千万]+)";

const RE_PER_CHAPTER_WORDS = new RegExp(
  `(?:每章|每回|单章)\\s*(${NUM})\\s*[kK千]?\\s*字|(${NUM})\\s*[kK千]?\\s*字\\s*[／/]\\s*[章回]`,
);
const RE_PER_VOLUME_CHAPTERS = new RegExp(`每卷\\s*(${NUM})\\s*[章回]`);
const RE_TOTAL_CHAPTERS = new RegExp(`(${NUM})\\s*[章回]`, "g");
const RE_TOTAL_WORDS_WAN = new RegExp(`(${NUM})\\s*[wW万]\\s*字`);
const RE_TOTAL_WORDS_QIAN = new RegExp(`(${NUM})\\s*[kK千]\\s*字`);
const RE_TOTAL_WORDS_PLAIN = new RegExp(
  `(?:共|全书|总字|总计|完本|整本|大约|约)\\s*(${NUM})\\s*字`,
);

/** 出现在数字**紧前面**的词 → 这个数字不是总量。 */
const NEGATIVE_SUFFIXES = [
  "每卷",
  "每回",
  "每章",
  "每",
  "第",
  "单",
  "上",
  "下",
  "另",
  "其余",
];

/** 把匹配到的数字文本转成 number（支持中文数字）。 */
function toNumber(raw: string | undefined): number | null {
  if (!raw) return null;
  const n = Number(raw);
  if (!Number.isNaN(n)) return n;
  const cn = cnToInt(raw);
  return cn === null ? null : cn;
}

/** 判断这个数字是不是"每卷 10 章"这类局部数字。 */
function isNegativeContext(text: string, start: number): boolean {
  const prefix = text.slice(Math.max(0, start - 4), start);
  for (const token of NEGATIVE_SUFFIXES) {
    if (prefix.endsWith(token)) return true;
  }
  const last = prefix[prefix.length - 1];
  if (last && /\d/.test(last)) return true;
  return false;
}

/**
 * 从作者的自然语言想法里解析规模参数。
 *
 * 支持："共100章" / "全书 100 章" / "每卷10章" / "每章3000字" / "30万字" / "30w字"
 *
 * @returns 解析出的规模；一个数都没识别出来时返回 `null`
 *   （调用方应保留原值，而不是把规模清零）
 */
export function parseScaleFromText(text: string): OutlineScale | null {
  if (!text || !text.trim()) return null;

  let perChapterWords: number | null = null;
  const mWords = RE_PER_CHAPTER_WORDS.exec(text);
  if (mWords) {
    const value = toNumber(mWords[1] ?? mWords[2]);
    if (value) {
      const mult = /[kK千]/.test(mWords[0]) ? 1000 : 1;
      perChapterWords = Math.round(value * mult);
    }
  }

  let perVolumeChapters: number | null = null;
  const mVol = RE_PER_VOLUME_CHAPTERS.exec(text);
  if (mVol) {
    const value = toNumber(mVol[1]);
    if (value) perVolumeChapters = Math.round(value);
  }

  let totalChapters: number | null = null;
  RE_TOTAL_CHAPTERS.lastIndex = 0;
  let mCh: RegExpExecArray | null;
  while ((mCh = RE_TOTAL_CHAPTERS.exec(text)) !== null) {
    // 匹配从数字开始（捕获组在模式首位）→ index 就是数字的位置
    if (isNegativeContext(text, mCh.index)) continue;
    const value = toNumber(mCh[1]);
    if (value) {
      totalChapters = Math.round(value);
      break;
    }
  }

  let totalWords: number | null = null;
  for (const [pattern, mult] of [
    [RE_TOTAL_WORDS_WAN, 10000],
    [RE_TOTAL_WORDS_QIAN, 1000],
    [RE_TOTAL_WORDS_PLAIN, 1],
  ] as const) {
    const m = pattern.exec(text);
    if (m) {
      const value = toNumber(m[1]);
      if (value) {
        totalWords = Math.round(value * mult);
        break;
      }
    }
  }

  // 只有总字数 → 按每章字数折算章数
  if (totalChapters === null && totalWords !== null) {
    const wpc = perChapterWords ?? DEFAULT_OUTLINE_SCALE.wordsPerChapter;
    totalChapters = Math.max(1, Math.round(totalWords / wpc));
  }
  // 只有总章数 + 总字数 → 反推每章字数
  if (perChapterWords === null && totalWords !== null && totalChapters) {
    perChapterWords = Math.max(1, Math.round(totalWords / totalChapters));
  }

  if (
    totalChapters === null &&
    perVolumeChapters === null &&
    perChapterWords === null
  ) {
    return null;
  }

  return normalizeScale({
    totalChapters: totalChapters ?? undefined,
    chaptersPerVolume: perVolumeChapters ?? undefined,
    wordsPerChapter: perChapterWords ?? undefined,
  });
}
