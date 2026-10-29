/**
 * 三条流的 AbortController 注册表（**模块级**）。
 *
 * 为什么用模块级变量而不是 useRef
 * -------------------------------
 * 组件卸载后 ref 还在但没人能拿到它 → 后台正在跑的生成就停不掉了。
 * 模块级变量任何时候都能访问（另一个 hook / 另一个组件都能中断）。
 *
 * ⚠️ 2026-10-25 巡检：以前只有「离开页面就 abort」和「不 abort」两个极端，
 *    后来改成"切页不打断、生成跑完写进 store"，但**手动停止**仍然要有 ——
 *    用户点「停止」必须真的断掉请求，否则后端还在烧 token。
 *
 * ⚠️ 2026-10-29 巡检：清理时必须**按身份**清除。
 *    旧的一条流的 `finally` 会在新的一条流登记之后才跑到 —— 如果无脑置空，
 *    新流就再也停不掉了（用户点了「停止」没反应）。
 */

/** 剧情生成（3 个版本并行）。 */
let plotAbort: AbortController | null = null;
/** 大纲生成（两阶段）。 */
let outlineAbort: AbortController | null = null;
/** 人物卡生成。 */
let charAbort: AbortController | null = null;

/** 登记剧情流的 controller。 */
export function setPlotAbort(ctrl: AbortController): void {
  plotAbort = ctrl;
}

/**
 * 清除剧情流的 controller。
 *
 * @param ctrl 要清除的 controller —— 只有它仍是当前登记的那个才清空，
 *             避免旧流的 finally 清掉新流的 controller。
 */
export function clearPlotAbort(ctrl: AbortController): void {
  if (plotAbort === ctrl) plotAbort = null;
}

/** 登记大纲流的 controller。 */
export function setOutlineAbort(ctrl: AbortController): void {
  outlineAbort = ctrl;
}

/**
 * 清除大纲流的 controller（按身份清除）。
 *
 * @param ctrl 要清除的 controller
 */
export function clearOutlineAbort(ctrl: AbortController): void {
  if (outlineAbort === ctrl) outlineAbort = null;
}

/** 登记人物卡流的 controller。 */
export function setCharAbort(ctrl: AbortController): void {
  charAbort = ctrl;
}

/**
 * 清除人物卡流的 controller（按身份清除）。
 *
 * @param ctrl 要清除的 controller
 */
export function clearCharAbort(ctrl: AbortController): void {
  if (charAbort === ctrl) charAbort = null;
}

/** 中断剧情生成（没有在跑时是空操作）。 */
export function abortPlot(): void {
  plotAbort?.abort();
}

/** 中断大纲生成。 */
export function abortOutline(): void {
  outlineAbort?.abort();
}

/** 中断人物卡生成。 */
export function abortChar(): void {
  charAbort?.abort();
}
