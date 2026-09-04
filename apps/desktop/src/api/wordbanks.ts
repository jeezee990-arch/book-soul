import { callApi } from "./index";
import type { WordbankList, WordbankMeta } from "@/lib/types";

/**
 * 词库 API 客户端（Phase 3.1）。
 *
 * 端点：
 * - list()              → GET /wordbanks
 * - getMeta(genre)      → GET /wordbanks/{genre}
 * - getRandom(genre, categories, n)
 *      → GET /wordbanks/{genre}/words?category=...&category=...&n=10
 *      单类返回 list[str]，多类返回 {cat: [str]}。
 */

export const wordbanksApi = {
  list: () => callApi<WordbankList>("GET", "/wordbanks"),

  getMeta: (genre: string) =>
    callApi<WordbankMeta>("GET", `/wordbanks/${genre}`),

  getRandom: (
    genre: string,
    categories: string[],
    n: number = 10,
  ): Promise<string[] | Record<string, string[]>> => {
    if (categories.length === 0) {
      throw new Error("categories must not be empty");
    }
    // 多值用 append（默认 set 会覆盖），让 FastAPI 收到 ?category=a&category=b
    const q = new URLSearchParams();
    for (const c of categories) q.append("category", c);
    q.set("n", String(n));
    return callApi<string[] | Record<string, string[]>>(
      "GET",
      `/wordbanks/${genre}/words?${q.toString()}`,
    );
  },
};
