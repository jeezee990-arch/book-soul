/**
 * 请求序号守卫（2026-10-29，种子库切换板块的响应乱序竞态）。
 *
 * 问题
 * ----
 * 种子库管理弹窗切换板块时，每个板块都会发一次 ``getAllWords``。
 * 网络抖动时，**先发起的 A 板块请求可能后到**，把已经切到 B 的列表覆盖成 A：
 *
 * ```
 * 点 A → 请求 A 发出
 * 点 B → 请求 B 发出，B 先回 → setData(B)  ✅
 *      → A 后到            → setData(A)  ❌ Tab 显示 B、列表却是 A
 * ```
 *
 * 危险的地方在于：Tab 显示的是 B，但列表是 A 的词，
 * 而所有写操作（删除/改名）都按当前板块 B 执行 ——
 * 用户看着 A 的列表，误删的却是 B 的词条。
 *
 * 做法
 * ----
 * 每次请求领一个**递增序号**，响应回来时只认序号最大的那次。
 * 早到的旧响应序号落后 → 直接丢弃，不碰 state。
 *
 * @example
 * ```ts
 * const guard = createRequestGuard();
 * const seq = guard.next();
 * const data = await api.get(gid);
 * if (!guard.isCurrent(seq)) return;  // 已有更新的请求了，丢弃
 * setData(data);
 * ```
 */
export interface RequestGuard {
  /** 领一个新序号（每次调用都会让之前的序号失效）。 */
  next: () => number;
  /** 某个序号是否仍是"最新那一次"。 */
  isCurrent: (seq: number) => boolean;
}

/**
 * 模块级全局计数器 —— 让序号在**所有守卫实例之间也唯一**。
 *
 * 为什么不用每个守卫各自从 1 开始：那样两个守卫会领到同样的序号
 * （都是 1），一旦序号被跨守卫误用，"isCurrent"就会误判为真。
 * 全局递增可以从根上避免这种碰撞。
 */
let globalSeq = 0;

/**
 * 创建一个请求序号守卫。
 *
 * @returns 守卫实例
 */
export function createRequestGuard(): RequestGuard {
  let current = 0;
  return {
    next: () => {
      globalSeq += 1;
      current = globalSeq;
      return current;
    },
    isCurrent: (seq: number) => seq === current,
  };
}
