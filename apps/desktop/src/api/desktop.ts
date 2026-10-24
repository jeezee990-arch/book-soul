/**
 * 桌面壳专属能力的封装（Tauri command）。
 *
 * 与 `api/backend.ts` 的区别：那里是"和 Python 后端说话"，这里是"和 Rust 壳说话" ——
 * 后端地址、数据目录、打开文件夹这类只有桌面版才有的能力。
 *
 * 纯浏览器（vite dev，没起 Tauri）下 invoke 会失败，调用方要能优雅降级。
 */

import { invoke } from "@tauri-apps/api/core";

export const desktopApi = {
  /** 在系统文件管理器中打开数据目录（设置页「在文件夹中显示」）。 */
  openDataDir: () => invoke<void>("open_data_dir"),
};
