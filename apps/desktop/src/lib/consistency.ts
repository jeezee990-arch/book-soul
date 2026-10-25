/**
 * 一致性检查（2026-10-25 新增）。
 *
 * 对应需求：
 * - 「剧情生成，自定义录入剧情词条，同时**检测是否符合种子词条**」
 * - 「大纲生成质量，以及**检测是否符合剧情走向**」
 *
 * ⚠️ 这是**词面**检查，不是语义理解
 * --------------------------------
 * - **种子词条**：精确子串匹配 —— 可靠，作者自己写的词，模型没提到就是没提到。
 * - **剧情走向**：中文 2-gram 词频做**词面重合度** —— 近似。
 *
 * 目的是给作者一个**可行动的信号**（重合度低 → 重新生成 / 调整想法），
 * 不是给模型打绩效分。所以 UI 上写的是"覆盖"而不是"合规/违规"。
 */

/** 覆盖结果。 */
export interface Coverage {
  /** 检查了多少项 */
  total: number;
  /** 命中的项 */
  matched: string[];
  /** 没命中的项 */
  missing: string[];
  /** 命中率（0-1；total 为 0 时为 1） */
  ratio: number;
}

/** 空结果。 */
const EMPTY: Coverage = { total: 0, matched: [], missing: [], ratio: 1 };

/**
 * 检查文本里是否覆盖了给定的词条（精确子串）。
 *
 * @param text 被检查的文本
 * @param keywords 词条列表（空词条忽略）
 */
export function checkKeywordCoverage(
  text: string,
  keywords: string[] | null | undefined,
): Coverage {
  const list = (keywords ?? []).map((k) => k.trim()).filter(Boolean);
  if (list.length === 0) return EMPTY;
  const haystack = text ?? "";
  const matched: string[] = [];
  const missing: string[] = [];
  for (const kw of list) {
    if (haystack.includes(kw)) matched.push(kw);
    else missing.push(kw);
  }
  return {
    total: list.length,
    matched,
    missing,
    ratio: matched.length / list.length,
  };
}

/**
 * 从文本里抽取"关键短语"（中文 2-gram 词频近似）。
 *
 * 为什么用 2-gram：中文没有分词器，2 字词（修仙 / 宗门 / 复仇）大多是真词，
 * 比 3-4 gram 噪声小得多。
 *
 * @param text 源文本
 * @param limit 最多取几个
 */
export function extractKeyTerms(text: string, limit = 8): string[] {
  const cleaned = (text ?? "").replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, " ");
  const counts = new Map<string, number>();
  for (const seg of cleaned.split(/\s+/)) {
    if (seg.length < 2) continue;
    for (let i = 0; i + 2 <= seg.length; i++) {
      const gram = seg.slice(i, i + 2);
      counts.set(gram, (counts.get(gram) ?? 0) + 1);
    }
  }
  // 只保留出现 ≥2 次的（一次出现的多半是噪声）
  const candidates = [...counts.entries()]
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length);
  const picked: string[] = [];
  for (const [gram] of candidates) {
    // 被已选词包含的跳过（避免"修仙"和"修仙女"重复计分）
    if (picked.some((p) => p.includes(gram))) continue;
    picked.push(gram);
    if (picked.length >= limit) break;
  }
  return picked;
}

/** 把大纲结构摊平成一段文本（用于词面比对）。 */
export function structureToText(structure: unknown): string {
  if (!structure || typeof structure !== "object") return "";
  const parts: string[] = [];
  const s = structure as Record<string, unknown>;
  const push = (value: unknown) => {
    if (typeof value === "string" && value.trim()) parts.push(value.trim());
  };
  push(s.overall_theme);
  push(s.summary);
  const volumes = Array.isArray(s.volumes) ? s.volumes : [];
  for (const raw of volumes) {
    if (!raw || typeof raw !== "object") continue;
    const v = raw as Record<string, unknown>;
    push(v.name);
    push(v.summary);
    const chapters = Array.isArray(v.chapters) ? v.chapters : [];
    for (const rawChapter of chapters) {
      if (!rawChapter || typeof rawChapter !== "object") continue;
      const c = rawChapter as Record<string, unknown>;
      push(c.title);
      push(c.summary);
      const events = Array.isArray(c.key_events) ? c.key_events : [];
      for (const e of events) push(e);
    }
  }
  return parts.join("\n");
}

/**
 * 检查大纲是否"沿着剧情走"（词面重合度）。
 *
 * @param structure 大纲结构
 * @param plotSummary 选中的那条剧情摘要
 */
export function checkOutlineCoverage(
  structure: unknown,
  plotSummary: string,
): Coverage {
  const terms = extractKeyTerms(plotSummary ?? "");
  if (terms.length === 0) return EMPTY;
  const outlineText = structureToText(structure);
  const matched: string[] = [];
  const missing: string[] = [];
  for (const term of terms) {
    if (outlineText.includes(term)) matched.push(term);
    else missing.push(term);
  }
  return {
    total: terms.length,
    matched,
    missing,
    ratio: matched.length / terms.length,
  };
}

/** 覆盖率的展示文案（0-100 的整数）。 */
export function coveragePercent(coverage: Coverage): number {
  if (coverage.total === 0) return 100;
  return Math.round(coverage.ratio * 100);
}
