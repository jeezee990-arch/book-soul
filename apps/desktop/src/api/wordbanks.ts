import { callApi } from "./index";
import { getBackendUrl } from "./backend";
import type {
  WordbankAllWords,
  WordbankImportResult,
  WordbankList,
  WordbankMeta,
  WordbankMutationResult,
  WordItem,
} from "@/lib/types";

/**
 * 词库 API 客户端（Phase 3.1 读 / 需求6 读写管理）。
 *
 * 端点：
 * - list()              → GET /wordbanks
 * - getMeta(genre)      → GET /wordbanks/{genre}
 * - getRandom(genre, categories, n)
 *      → GET /wordbanks/{genre}/words?category=...&category=...&n=10
 *      单类返回 list[str]，多类返回 {cat: [str]}。
 * - getAllWords(genre)  → GET /wordbanks/{genre}/all-words（管理弹窗用）
 * - addWords / updateWord / deleteWords → POST / PATCH / DELETE .../words
 * - importText(genre, text, category)   → POST .../import（粘贴文本）
 * - importFile(genre, file, category)   → POST .../import-file（文件，原始 body）
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

  /** 该板块的全部词条（按分类分组）。 */
  getAllWords: (genre: string) =>
    callApi<WordbankAllWords>("GET", `/wordbanks/${genre}/all-words`),

  /** 新增词条（单个或批量）。 */
  addWords: (genre: string, items: WordItem[]) =>
    callApi<WordbankMutationResult>("POST", `/wordbanks/${genre}/words`, { items }),

  /** 修改词条（把 category 里的 old 改成 new）。 */
  updateWord: (genre: string, category: string, old: string, next: string) =>
    callApi<WordbankMutationResult>("PATCH", `/wordbanks/${genre}/words`, {
      category,
      old,
      new: next,
    }),

  /** 删除词条（支持批量）。 */
  deleteWords: (genre: string, items: WordItem[]) =>
    callApi<WordbankMutationResult>("DELETE", `/wordbanks/${genre}/words`, { items }),

  /** 粘贴文本导入。 */
  importText: (genre: string, text: string, defaultCategory: string = "themes") =>
    callApi<WordbankImportResult>("POST", `/wordbanks/${genre}/import`, {
      text,
      default_category: defaultCategory,
    }),
};

/**
 * 文件导入：把文件内容当**原始 body** 发给后端。
 *
 * ⚠️ 为什么不用 `callApi`：那条通道走 Tauri invoke，只能发 JSON；
 * 而后端这个端点收的是纯文本 body（种子词本来就是文本，
 * 不值得为它引入 python-multipart 依赖）。
 * 直接 fetch 后端地址在桌面版 / 浏览器版都成立（流式接口也是这么绕的）。
 */
export async function importWordbankFile(
  genre: string,
  file: File,
  defaultCategory: string = "themes",
): Promise<WordbankImportResult> {
  const base = (await getBackendUrl()).replace(/\/$/, "");
  const url = `${base}/wordbanks/${encodeURIComponent(genre)}/import-file?default_category=${encodeURIComponent(defaultCategory)}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
    body: await file.text(),
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      detail = (await resp.text()) || detail;
    } catch {
      // 忽略读 body 失败
    }
    throw new Error(`导入失败：${detail}`);
  }
  return (await resp.json()) as WordbankImportResult;
}
