/**
 * 灵感园的类型定义。
 *
 * 单独抽出来是为了让 `index.tsx`（状态机 + 流式请求）和各个视图组件
 * 共享同一份类型，避免视图文件反向 import 主组件造成循环依赖。
 */

/** 灵感园流程状态机的状态。 */
export type Step =
  | "idle"
  | "seed"
  | "plot_stream"
  | "plot_review"
  | "outline_stream"
  | "character_stream"
  | "done";

/** 一个剧情版本（LLM 生成的第 N 版剧情梗概）。 */
export interface PlotVersion {
  /** 版本序号，从 1 开始 */
  index: number;
  /** 剧情梗概正文 */
  summary: string;
}

/** 大纲生成完成后落库的"作品"元信息。 */
export interface NovelState {
  id: number;
  name: string;
  outlineStructure: Record<string, unknown>;
}

/** 人物卡生成进度。 */
export interface CharProgress {
  /** 抽取阶段识别出的人物（name + role） */
  extracted: { name: string; role: string }[];
  /** 逐张生成中的人物卡（id 在入库后才出现） */
  cards: { name: string; role: string; id?: number; text: string }[];
  /** 错误信息 */
  error?: string;
}

/** 空的人物卡进度（用于重置）。 */
export const EMPTY_CHAR_PROGRESS: CharProgress = { extracted: [], cards: [] };

/**
 * 一次生成的结果统计（用户要求显示"当前模型 + 耗时多少秒"）。
 *
 * - `model`：这次实际用的模型名（后端从 provider 配置读出来的，不是前端猜的）
 * - `elapsedSec`：整个生成流程的耗时（秒）
 * - `firstDeltaSec`：首字延迟（秒）—— 从发起到吐出第一个正文字符
 */
export interface GenStats {
  model: string;
  elapsedSec: number;
  firstDeltaSec: number | null;
}
