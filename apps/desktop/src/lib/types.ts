/**
 * 后端 Pydantic Read 模型的 TS 镜像。
 * 与 server/src/schemas/*.py 保持字段一致。
 */

export interface Novel {
  id: number;
  name: string;
  genre: string;
  style: string | null;
  description: string | null;
  status: string;
  outline_mode: string | null;
  file_path: string | null;
  imported: boolean;
  read_only: boolean;
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: number;
  novel_id: number;
  name: string;
  role: string;
  basic_info: string | null;
  personality: string | null;
  habits: string | null;
  thinking: string | null;
  relationships: string | null;
  growth_arc: string | null;
  current_version_id: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CharacterVersion {
  id: number;
  character_id: number;
  parent_version_id: number | null;
  snapshot: Record<string, unknown>;
  change_reason: string;
  trigger_event: string | null;
  created_at: string;
}

export interface CharacterGrowthEvent {
  event: string;
  new_personality?: string | null;
  new_habits?: string | null;
  new_thinking?: string | null;
  new_relationships?: string | null;
}

export interface Chapter {
  id: number;
  novel_id: number;
  chapter_number: number;
  title: string | null;
  outline: string | null;
  status: string;
  current_version_id: number | null;
  word_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChapterVersion {
  id: number;
  chapter_id: number;
  parent_version_id: number | null;
  content: string;
  diff: string | null;
  trigger: string;
  prompt: string | null;
  metadata: Record<string, unknown> | null;
  word_count: number;
  created_at: string;
}

export interface Outline {
  id: number;
  novel_id: number;
  outline_type: string;
  structure: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ===== 大纲 structure 的 TS 镜像（对齐 server/src/schemas/outline.py）=====

/** complete 结构里的章节节点。 */
export interface OutlineChapterNode {
  title: string;
  summary?: string | null;
  key_events?: string[];
}

/** complete 结构里的卷节点。 */
export interface OutlineVolumeNode {
  name: string;
  summary?: string | null;
  chapters?: OutlineChapterNode[];
}

/** complete：分卷 > 章 > 关键事件。 */
export interface CompleteOutlineStructure {
  volumes?: OutlineVolumeNode[];
  overall_theme?: string | null;
}

/** freedom：自由文字 + 关键节拍 + 主题。 */
export interface FreedomOutlineStructure {
  summary?: string;
  key_beats?: string[];
  themes?: string[];
}

export interface Inspiration {
  id: number;
  novel_id: number | null;
  type: string;
  source: string | null;
  tags: string[];
  content: Record<string, unknown>;
  created_at: string;
}

// ===== 词库（Phase 3.1）=====

export interface WordbankListEntry {
  id: string;
  name: string;
  total: number;
}

export interface WordbankList {
  genres: WordbankListEntry[];
}

export interface WordbankMeta {
  id: string;
  name: string;
  categories: string[];
  counts: Record<string, number>;
}
