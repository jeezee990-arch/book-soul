/**
 * 聊天模块的后端 API 封装（2026-10-25 新增）。
 *
 * 三层结构：项目 → 对话 → 消息。
 * 流式发消息走 `readNdjsonStream`（前端直连后端，不经过 Rust）。
 */

import { callApi } from "./index";
import type { StreamRequest } from "./streams";

export interface ChatProject {
  id: number;
  name: string;
  description: string | null;
  /** 接入的素材 id（对应 inspirations.id） */
  materials: number[];
  created_at: string;
  updated_at: string;
}

export interface ChatConversation {
  id: number;
  project_id: number;
  title: string;
  model: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  model: string | null;
  created_at: string;
}

export const chatApi = {
  // ===== 项目 =====
  listProjects: () => callApi<ChatProject[]>("GET", "/chat/projects"),
  createProject: (data: { name: string; description?: string | null }) =>
    callApi<ChatProject>("POST", "/chat/projects", data),
  updateProject: (
    id: number,
    data: { name?: string; description?: string | null; materials?: number[] },
  ) => callApi<ChatProject>("PATCH", `/chat/projects/${id}`, data),
  removeProject: (id: number) =>
    callApi<null>("DELETE", `/chat/projects/${id}`),
  /** 接入素材（整体替换） */
  setMaterials: (id: number, inspirationIds: number[]) =>
    callApi<ChatProject>("PUT", `/chat/projects/${id}/materials`, {
      inspiration_ids: inspirationIds,
    }),

  // ===== 对话 =====
  listConversations: (projectId: number) =>
    callApi<ChatConversation[]>("GET", `/chat/projects/${projectId}/conversations`),
  createConversation: (projectId: number, title = "新对话") =>
    callApi<ChatConversation>("POST", `/chat/projects/${projectId}/conversations`, {
      title,
    }),
  updateConversation: (
    id: number,
    data: { title?: string; model?: string | null },
  ) => callApi<ChatConversation>("PATCH", `/chat/conversations/${id}`, data),
  removeConversation: (id: number) =>
    callApi<null>("DELETE", `/chat/conversations/${id}`),

  // ===== 消息 =====
  listMessages: (conversationId: number) =>
    callApi<ChatMessage[]>("GET", `/chat/conversations/${conversationId}/messages`),

  /** 流式发消息（ndjson）。 */
  sendStream: (
    conversationId: number,
    content: string,
    signal?: AbortSignal,
  ): StreamRequest => ({
    url: `/chat/conversations/${conversationId}/messages/stream`,
    method: "POST",
    body: { content },
    signal,
  }),
};
