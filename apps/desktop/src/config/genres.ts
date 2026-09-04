/**
 * 题材优先级与元数据（前端展示用）。
 *
 * - id 必须与后端 ``config/wordbanks/{id}.yaml`` 文件名一致
 * - tier 是 JEE 决策的优先级（P0 最高，做得最深）
 * - 数组顺序即 UI 展示顺序
 *
 * 后端题材数据来源：``config/genres/{id}.yaml``、``config/wordbanks/{id}.yaml``。
 */

export type GenreTier = "P0" | "P1" | "P2" | "P3";

export interface GenreDef {
  id: string;
  name: string;
  tier: GenreTier;
  emoji: string;
}

export const GENRE_PRIORITY: readonly GenreDef[] = [
  { id: "xiuxian", name: "修仙", tier: "P0", emoji: "🗡️" },
  { id: "dushi", name: "都市", tier: "P1", emoji: "🏙️" },
  { id: "xuanyi", name: "悬疑", tier: "P2", emoji: "🔍" },
  { id: "yanqing", name: "言情", tier: "P3", emoji: "💕" },
] as const;

export function getGenreDef(id: string): GenreDef | undefined {
  return GENRE_PRIORITY.find((g) => g.id === id);
}
