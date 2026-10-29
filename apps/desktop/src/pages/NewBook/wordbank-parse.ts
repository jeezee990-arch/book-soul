/**
 * 词库管理的纯逻辑（导入预解析 + 中文标签映射）。
 *
 * 为什么要前端也解析一遍：用户在点「导入」之前就该看到
 * "这批文本会被拆成多少个词、哪几行有问题"，而不是提交完才知道。
 *
 * ⚠️ 规则必须与后端 ``server/src/services/wordbank_importer.py`` 保持一致 ——
 * 后端才是权威（它会再解析一遍并去重），前端这份只用于**预览**。
 */

/** 分类 key → 中文标签（与后端 CATEGORY_LABELS 一致）。 */
export const CATEGORY_LABELS: Record<string, string> = {
  themes: "主题",
  characters: "人物",
  plots: "情节",
  scenes: "场景",
  items: "物品",
};

/** 分类别名 → 规范 key（英文 key + 中文别名）。 */
export const CATEGORY_ALIASES: Record<string, string> = {
  themes: "themes",
  theme: "themes",
  characters: "characters",
  character: "characters",
  plots: "plots",
  plot: "plots",
  scenes: "scenes",
  scene: "scenes",
  items: "items",
  item: "items",
  主题: "themes",
  主题词: "themes",
  题材: "themes",
  人物: "characters",
  人物卡: "characters",
  角色: "characters",
  情节: "plots",
  剧情: "plots",
  桥段: "plots",
  场景: "scenes",
  环境: "scenes",
  物品: "items",
  道具: "items",
  法宝: "items",
};

/** 词条最长长度（与后端一致）。 */
export const MAX_WORD_LENGTH = 60;

/** 分类 key 的中文标签（认不出来就原样返回 key）。 */
export function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key;
}

/**
 * 板块 id → 中文名。
 *
 * @param id 板块 id（如 xiuxian）
 * @param name 后端返回的板块名（有就用后端的 —— 它来自 YAML，最准）
 */
export function genreLabel(id: string, name?: string | null): string {
  if (name && name.trim()) return name.trim();
  return id;
}

/** 解析出来的词条。 */
export interface ParsedImportWord {
  category: string;
  word: string;
  lineNo: number;
}

/** 解析失败的一行。 */
export interface ParsedImportIssue {
  lineNo: number;
  raw: string;
  reason: string;
}

/** 一次预解析的结果。 */
export interface ParsedImport {
  words: ParsedImportWord[];
  issues: ParsedImportIssue[];
  /** 批次内重复条数。 */
  duplicates: number;
}

const DELIMITER_RE = /[,，、;；|\t]+/;
const LEADING_PREFIX_RE = /^([^:：,，、;；|\t]{1,20})[:：]\s*(.*)$/;
const TOKEN_PREFIX_RE = /^([^:：]{1,20})[:：]\s*(.+)$/;

/**
 * 把用户写的分类前缀解析成规范分类 key。
 *
 * @param raw 前缀原文（themes / 主题 / THEMES）
 * @param validCategories 当前板块实际有的分类（认不出来就返回 null）
 */
export function resolveCategory(
  raw: string,
  validCategories: string[],
): string | null {
  const key = raw.trim().toLowerCase();
  if (!key) return null;
  if (validCategories.includes(key)) return key;
  const mapped = CATEGORY_ALIASES[key];
  if (!mapped) return null;
  if (!validCategories.includes(mapped)) return null;
  return mapped;
}

/**
 * 预解析导入文本（预览用）。
 *
 * @param text 原始文本
 * @param defaultCategory 没写分类前缀的词归到哪类
 * @param validCategories 当前板块有的分类
 */
export function parseImportText(
  text: string,
  defaultCategory: string,
  validCategories: string[],
): ParsedImport {
  const words: ParsedImportWord[] = [];
  const issues: ParsedImportIssue[] = [];
  const seen = new Set<string>();
  let duplicates = 0;

  const lines = text.split(/\r?\n/);
  lines.forEach((rawLine, idx) => {
    const lineNo = idx + 1;
    const trimmed = rawLine.trim();
    if (!trimmed) return;
    if (trimmed.startsWith("#") || trimmed.startsWith("//")) return;

    // 行首分类前缀（作用于整行）
    let lineCategory: string | null = null;
    let body = trimmed;
    const lead = LEADING_PREFIX_RE.exec(trimmed);
    if (lead) {
      const resolved = resolveCategory(lead[1], validCategories);
      if (!resolved) {
        issues.push({
          lineNo,
          raw: trimmed,
          reason: `无法识别的分类「${lead[1].trim()}」`,
        });
        return;
      }
      lineCategory = resolved;
      body = lead[2];
    }

    for (const rawToken of body.split(DELIMITER_RE)) {
      let token = rawToken.trim();
      if (!token) continue;

      // 词条自带分类前缀（覆盖行首前缀）
      let category = lineCategory ?? defaultCategory;
      const tokenPrefix = TOKEN_PREFIX_RE.exec(token);
      if (tokenPrefix) {
        const resolved = resolveCategory(tokenPrefix[1], validCategories);
        if (!resolved) {
          issues.push({
            lineNo,
            raw: trimmed,
            reason: `无法识别的分类「${tokenPrefix[1].trim()}」`,
          });
          continue;
        }
        category = resolved;
        token = tokenPrefix[2].trim();
      }

      if (!token) {
        issues.push({ lineNo, raw: trimmed, reason: "词条为空" });
        continue;
      }
      if (token.length > MAX_WORD_LENGTH) {
        issues.push({
          lineNo,
          raw: trimmed,
          reason: `词条过长（${token.length} 字，上限 ${MAX_WORD_LENGTH}）`,
        });
        continue;
      }

      const key = `${category}::${token}`;
      if (seen.has(key)) {
        duplicates += 1;
        continue;
      }
      seen.add(key);
      words.push({ category, word: token, lineNo });
    }
  });

  return { words, issues, duplicates };
}

/** 一行摘要（预览用）："12 个词条 · 2 行有问题 · 1 个重复"。 */
export function summarizeImport(parsed: ParsedImport): string {
  const parts = [`${parsed.words.length} 个词条`];
  if (parsed.duplicates > 0) parts.push(`${parsed.duplicates} 个重复`);
  if (parsed.issues.length > 0) parts.push(`${parsed.issues.length} 行有问题`);
  return parts.join(" · ");
}
