/**
 * 词库批量拉取。
 *
 * 从 wordbank API 拉一批随机词：多分类合并 → 去重 → 排除已选 → 截断到 n 条。
 *
 * 单独抽出来是因为它是一个**纯函数式的网络调用**，和视图渲染无关，
 * 放在一起会让 SeedView 文件变得又长又难读。
 */

import { wordbanksApi } from "@/api/wordbanks";

/**
 * 拉一批随机词（多分类合并、去重、避开已选）。
 *
 * @param genreId 题材 id
 * @param categories 词条分类；为空时直接返回空数组
 * @param n 最多返回多少条
 * @param exclude 需要排除的词（通常是已选中的）
 */
export async function fetchRandomBatch(
  genreId: string,
  categories: string[],
  n: number,
  exclude: Set<string>,
): Promise<string[]> {
  if (categories.length === 0) return [];
  // 多个分类各取 n 个，merge 后 shuffle
  const results = await Promise.all(
    categories.map((cat) =>
      wordbanksApi.getRandom(genreId, [cat], n).catch(() => []),
    ),
  );
  const merged: string[] = [];
  for (const r of results) {
    if (Array.isArray(r)) merged.push(...r);
    else if (r && typeof r === "object") {
      for (const list of Object.values(r)) merged.push(...list);
    }
  }
  // 去重 + 排除已选
  const seen = new Set<string>();
  const out: string[] = [];
  for (const w of merged) {
    if (exclude.has(w) || seen.has(w)) continue;
    seen.add(w);
    out.push(w);
    if (out.length >= n) break;
  }
  return out;
}
