/**
 * 作品命名相关的纯逻辑（2026-10-30）。
 *
 * 为什么要单独抽出来
 * --------------------
 * 「素材库里只能有一本同名作品」这条规则**前后端都要执行**：
 *
 * - 后端：``NovelService.name_taken`` / ``unique_name``（权威，拦得住并发）
 * - 前端：输入时立刻提示"已有同名作品"，别等提交了才报错
 *
 * 两边的规则必须**一模一样**，否则用户会看到"前端说不冲突、后端说冲突"。
 * 所以规则写在这里（前端） + 后端同名方法，后端为准，前端跟着走。
 *
 * 规则：
 * - 名字比较：**去掉首尾空白后**精确匹配（与后端一致；后端不做大小写折叠，
 *   所以「A Book」和「a book」是两本不同的书）
 * - 自动避让：``X`` → ``X 2`` → ``X 3`` …
 */

/**
 * 名字是否已被占用。
 *
 * @param name - 待检查的名字
 * @param existing - 已存在的名字集合（任意可迭代对象）
 * @returns true 表示已经有人用了这个名字
 */
export function isNameTaken(name: string, existing: Iterable<string>): boolean {
  const target = name.trim();
  if (!target) return false;
  for (const item of existing) {
    if (item.trim() === target) return true;
  }
  return false;
}

/**
 * 找一个没人占用的名字。
 *
 * 与后端 ``NovelService.unique_name`` 规则一致：
 * 没人用就原样返回；被占了就在后面加序号（``X`` → ``X 2`` → ``X 3`` …）。
 *
 * @param base - 基础名
 * @param existing - 已存在的名字集合
 * @returns 可用的名字
 */
export function uniqueName(base: string, existing: Iterable<string>): string {
  const trimmed = base.trim();
  if (!trimmed) return trimmed;
  const taken = new Set<string>();
  for (const item of existing) taken.add(item.trim());
  if (!taken.has(trimmed)) return trimmed;
  let index = 2;
  while (taken.has(`${trimmed} ${index}`)) index += 1;
  return `${trimmed} ${index}`;
}

/**
 * 重名提示信息。
 *
 * @param name - 用户输入的名字
 * @param existing - 已存在的名字集合
 * @param excludeName - 要排除的名字（改名时排除自己那本）
 * @returns 提示文案；不重名时返回 null
 */
export function duplicateHint(
  name: string,
  existing: Iterable<string>,
  excludeName?: string | null,
): string | null {
  const trimmed = name.trim();
  if (!trimmed) return null;
  const others: string[] = [];
  for (const item of existing) {
    if (excludeName && item.trim() === excludeName.trim()) continue;
    others.push(item);
  }
  if (!isNameTaken(trimmed, others)) return null;
  return `素材库里已有同名作品「${trimmed}」，保存时会自动改为「${uniqueName(trimmed, others)}」`;
}
