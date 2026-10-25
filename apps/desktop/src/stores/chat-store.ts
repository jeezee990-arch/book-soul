/**
 * 聊天模块的状态（2026-10-25 新增）。
 *
 * 三层结构：项目 → 对话 → 消息。
 *
 * 为什么用 store 而不是组件 useState
 * ---------------------------------
 * 流式回复可能很长，用户会切到别的页面看看 —— 如果回复状态活在组件里，
 * 组件一卸载，正在生成的回复就"丢了"（用户回来发现空白）。
 * store 的 set 永远有效，切走再回来能看到完整结果。
 *
 * 持久化
 * ------
 * 只持久化"当前选中哪个项目/对话"（用户偏好）；
 * 消息与列表每次从后端拉（后端才是权威）。
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import { chatApi, type ChatConversation, type ChatMessage, type ChatProject } from "@/api/chat";
import {
  detectStreamFailure,
  parseChatStreamEvent,
  readNdjsonStream,
} from "@/api/streams";

interface ChatState {
  /** 项目列表 */
  projects: ChatProject[];
  /** 当前项目的对话列表 */
  conversations: ChatConversation[];
  /** 当前对话的消息 */
  messages: ChatMessage[];

  /** 当前选中的项目 id */
  currentProjectId: number | null;
  /** 当前选中的对话 id */
  currentConversationId: number | null;

  /** 左侧项目栏是否展开 */
  panelOpen: boolean;

  /** 正在流式接收的助手文本 */
  streamingText: string;
  /** 正在流式接收的思考文本 */
  streamingThinking: string;
  /** 是否正在生成 */
  busy: boolean;

  // ===== actions =====
  setPanelOpen: (open: boolean) => void;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<ChatProject | null>;
  renameProject: (id: number, name: string) => Promise<void>;
  deleteProject: (id: number) => Promise<void>;
  setMaterials: (id: number, inspirationIds: number[]) => Promise<void>;
  selectProject: (id: number | null) => Promise<void>;
  loadConversations: (projectId: number) => Promise<void>;
  createConversation: (projectId: number, title?: string) => Promise<void>;
  renameConversation: (id: number, title: string) => Promise<void>;
  deleteConversation: (id: number) => Promise<void>;
  selectConversation: (id: number | null) => Promise<void>;
  loadMessages: (conversationId: number) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  stopStreaming: () => void;
}

/** 模块级 AbortController（组件卸载后也能停）。 */
let chatAbort: AbortController | null = null;

export function createChatStore(storage?: StateStorage) {
  return create<ChatState>()(
    persist(
      (set, get) => ({
        projects: [],
        conversations: [],
        messages: [],
        currentProjectId: null,
        currentConversationId: null,
        panelOpen: true,
        streamingText: "",
        streamingThinking: "",
        busy: false,

        setPanelOpen: (panelOpen) => set({ panelOpen }),

        loadProjects: async () => {
          try {
            const projects = await chatApi.listProjects();
            set({ projects });
          } catch {
            set({ projects: [] });
          }
        },

        createProject: async (name) => {
          const trimmed = name.trim();
          if (!trimmed) return null;
          const project = await chatApi.createProject({ name: trimmed });
          set((s) => ({ projects: [project, ...s.projects] }));
          await get().selectProject(project.id);
          return project;
        },

        renameProject: async (id, name) => {
          const trimmed = name.trim();
          if (!trimmed) return;
          const updated = await chatApi.updateProject(id, { name: trimmed });
          set((s) => ({
            projects: s.projects.some((p) => p.id === id)
              ? s.projects.map((p) => (p.id === id ? updated : p))
              : [updated, ...s.projects],
          }));
        },

        deleteProject: async (id) => {
          await chatApi.removeProject(id);
          set((s) => ({
            projects: s.projects.filter((p) => p.id !== id),
            conversations:
              s.currentProjectId === id ? [] : s.conversations,
            messages: [],
            currentProjectId: s.currentProjectId === id ? null : s.currentProjectId,
            currentConversationId:
              s.currentProjectId === id ? null : s.currentConversationId,
          }));
        },

        setMaterials: async (id, inspirationIds) => {
          const updated = await chatApi.setMaterials(id, inspirationIds);
          set((s) => ({
            projects: s.projects.some((p) => p.id === id)
              ? s.projects.map((p) => (p.id === id ? updated : p))
              : [updated, ...s.projects],
          }));
        },

        selectProject: async (id) => {
          set({
            currentProjectId: id,
            currentConversationId: null,
            conversations: [],
            messages: [],
          });
          if (id === null) return;
          await get().loadConversations(id);
        },

        loadConversations: async (projectId) => {
          try {
            const conversations = await chatApi.listConversations(projectId);
            set({ conversations });
          } catch {
            set({ conversations: [] });
          }
        },

        createConversation: async (projectId, title = "新对话") => {
          const conversation = await chatApi.createConversation(projectId, title);
          set((s) => ({
            conversations: [conversation, ...s.conversations],
            currentConversationId: conversation.id,
            messages: [],
          }));
        },

        renameConversation: async (id, title) => {
          const trimmed = title.trim();
          if (!trimmed) return;
          const updated = await chatApi.updateConversation(id, { title: trimmed });
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === id ? updated : c,
            ),
          }));
        },

        deleteConversation: async (id) => {
          await chatApi.removeConversation(id);
          set((s) => ({
            conversations: s.conversations.filter((c) => c.id !== id),
            messages: s.currentConversationId === id ? [] : s.messages,
            currentConversationId:
              s.currentConversationId === id ? null : s.currentConversationId,
          }));
        },

        selectConversation: async (id) => {
          set({ currentConversationId: id, messages: [] });
          if (id === null) return;
          await get().loadMessages(id);
        },

        loadMessages: async (conversationId) => {
          try {
            const messages = await chatApi.listMessages(conversationId);
            // ⚠️ 2026-10-25 巡检：快速切换两个对话时，先发的请求可能后到
            //    → 直接 set 会把**上一个对话**的消息显示在当前对话下。
            //    只接受"仍然是当前对话"的响应。
            if (get().currentConversationId !== conversationId) return;
            set({ messages });
          } catch {
            if (get().currentConversationId === conversationId) {
              set({ messages: [] });
            }
          }
        },

        stopStreaming: () => {
          chatAbort?.abort();
          chatAbort = null;
          // ⚠️ **不要**清 streamingText：用户主动停止，已经吐出来的半截
          //    要留在屏幕上（后端也会把半截存下来）。
          //    原来这里清空 + 下面的 abort 被当成"聊天失败"弹红字 ——
          //    用户自己点的停止，反倒被报成错误（2026-10-25 巡检）。
          set({ busy: false });
        },

        sendMessage: async (content) => {
          const trimmed = content.trim();
          const conversationId = get().currentConversationId;
          if (!trimmed || conversationId === null || get().busy) return;

          set({ busy: true, streamingText: "", streamingThinking: "" });
          const ctrl = new AbortController();
          chatAbort = ctrl;
          const req = chatApi.sendStream(conversationId, trimmed, ctrl.signal);
          try {
            for await (const ev of readNdjsonStream(req.url, {
              method: req.method,
              body: req.body,
              signal: ctrl.signal,
            })) {
              // ⚠️ transport 与 server 两类失败都要认（AGENTS.md §4.10）
              const failure = detectStreamFailure(ev);
              if (failure) {
                set({ busy: false });
                throw new Error(failure.message);
              }
              const parsed = parseChatStreamEvent(ev);
              if (parsed.kind === "error") {
                set({ busy: false });
                throw new Error(parsed.message);
              }
              if (parsed.kind === "user_message") {
                set((s) => ({
                  messages: [...s.messages, parsed.message as ChatMessage],
                }));
              } else if (parsed.kind === "thinking") {
                set((s) => ({
                  streamingThinking: s.streamingThinking + parsed.text,
                }));
              } else if (parsed.kind === "delta") {
                set((s) => ({ streamingText: s.streamingText + parsed.text }));
              } else if (parsed.kind === "done") {
                set((s) => ({
                  messages: [...s.messages, parsed.message as ChatMessage],
                  streamingText: "",
                  streamingThinking: "",
                  busy: false,
                }));
              }
            }
          } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e);
            const aborted =
              msg.includes("abort") || msg.includes("aborted");
            if (!aborted) {
              // 真实错误才抛给调用方弹 toast；用户主动停止不算错误
              throw e;
            }
          } finally {
            chatAbort = null;
            set({ busy: false });
          }
        },
      }),
      {
        name: "book-soul-chat",
        partialize: (s) => ({
          currentProjectId: s.currentProjectId,
          currentConversationId: s.currentConversationId,
          panelOpen: s.panelOpen,
        }),
        ...(storage ? { storage: createJSONStorage(() => storage) } : {}),
      },
    ),
  );
}

/** 全局单例（应用里统一用这个）。 */
export const useChatStore = createChatStore();
