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

export interface Outline {
  id: number;
  novel_id: number;
  outline_type: string;
  structure: Record<string, unknown>;
  created_at: string;
  updated_at: string;
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
