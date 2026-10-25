/**
 * 聊天 store 的单元测试（2026-10-25 新增）。
 *
 * 覆盖：
 * - 项目 / 对话的增删改
 * - 选中项目 → 拉对话；选中对话 → 拉消息
 * - 素材接入
 * - 流式发消息：user_message → delta → done，消息都进列表
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const mem = new Map<string, string>();
const memoryStorage = {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => {
    mem.set(k, v);
  },
  removeItem: (k: string) => {
    mem.delete(k);
  },
};

// ===== mock api/chat =====
const projects = [
  {
    id: 1,
    name: "项目一",
    description: null,
    materials: [] as number[],
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
  },
];
const conversations = [
  {
    id: 10,
    project_id: 1,
    title: "主线",
    model: null,
    created_at: "2026-01-01",
    updated_at: "2026-01-01",
  },
];
const messages = [
  {
    id: 100,
    conversation_id: 10,
    role: "user" as const,
    content: "之前说的",
    model: null,
    created_at: "2026-01-01",
  },
];

const chatApiMock = {
  listProjects: vi.fn(async () => projects),
  createProject: vi.fn(async (data: { name: string }) => ({
    ...projects[0],
    id: 2,
    name: data.name,
  })),
  updateProject: vi.fn(async (id: number, data: { name?: string; materials?: number[] }) => ({
    ...projects[0],
    id,
    ...data,
  })),
  removeProject: vi.fn(async () => null),
  setMaterials: vi.fn(async (id: number, ids: number[]) => ({
    ...projects[0],
    id,
    materials: ids,
  })),
  listConversations: vi.fn(async () => conversations),
  createConversation: vi.fn(async () => conversations[0]),
  updateConversation: vi.fn(async (id: number, data: { title?: string }) => ({
    ...conversations[0],
    id,
    ...data,
  })),
  removeConversation: vi.fn(async () => null),
  listMessages: vi.fn(async () => messages),
  sendStream: vi.fn(() => ({
    url: "/chat/conversations/10/messages/stream",
    method: "POST" as const,
    body: { content: "hi" },
  })),
};

vi.mock("@/api/chat", () => ({ chatApi: chatApiMock }));

// ===== mock api/streams（只关心事件解析）=====
const streamEvents: unknown[] = [];
vi.mock("@/api/streams", () => ({
  readNdjsonStream: async function* () {
    for (const ev of streamEvents) yield ev;
  },
  detectStreamFailure: (ev: unknown) => {
    const o = ev as { error?: string; event?: string };
    if (typeof o.error === "string") return { source: "transport", message: o.error };
    if (o.event === "error") {
      return { source: "server", message: (ev as { message?: string }).message ?? "x" };
    }
    return null;
  },
  parseChatStreamEvent: (ev: unknown) => {
    const o = ev as Record<string, unknown>;
    switch (o.event) {
      case "user_message":
        return { kind: "user_message", message: o.message };
      case "thinking":
        return { kind: "thinking", text: o.text ?? "" };
      case "delta":
        return { kind: "delta", text: o.text ?? "" };
      case "done":
        return { kind: "done", message: o.message, model: o.model ?? "", elapsedSec: null };
      default:
        return { kind: "unknown" };
    }
  },
}));

const { createChatStore } = await import("../chat-store");

describe("chat-store", () => {
  let store: ReturnType<typeof createChatStore>;

  beforeEach(() => {
    mem.clear();
    streamEvents.length = 0;
    store = createChatStore(memoryStorage);
  });

  it("初始没有项目", () => {
    expect(store.getState().projects).toEqual([]);
    expect(store.getState().currentProjectId).toBeNull();
  });

  it("拉项目列表", async () => {
    await store.getState().loadProjects();
    expect(store.getState().projects).toHaveLength(1);
    expect(store.getState().projects[0].name).toBe("项目一");
  });

  it("新建项目 → 自动选中", async () => {
    const created = await store.getState().createProject("新项目");
    expect(created?.name).toBe("新项目");
    expect(store.getState().currentProjectId).toBe(2);
  });

  it("选中项目 → 拉对话", async () => {
    await store.getState().selectProject(1);
    expect(store.getState().conversations).toHaveLength(1);
    expect(store.getState().currentConversationId).toBeNull();
  });

  it("选中对话 → 拉消息", async () => {
    await store.getState().selectConversation(10);
    expect(store.getState().messages).toHaveLength(1);
    expect(store.getState().messages[0].content).toBe("之前说的");
  });

  it("接入素材", async () => {
    await store.getState().setMaterials(1, [5, 6]);
    const p = store.getState().projects.find((x) => x.id === 1);
    expect(p?.materials).toEqual([5, 6]);
  });

  it("删除项目 → 同时清掉当前选中", async () => {
    await store.getState().selectProject(1);
    await store.getState().deleteProject(1);
    expect(store.getState().currentProjectId).toBeNull();
    expect(store.getState().projects).toHaveLength(0);
  });

  it("流式发消息：用户消息 + 助手消息都进列表", async () => {
    await store.getState().selectConversation(10);
    streamEvents.push(
      { event: "user_message", message: { id: 1, conversation_id: 10, role: "user", content: "hi" } },
      { event: "delta", text: "你好" },
      { event: "done", message: { id: 2, conversation_id: 10, role: "assistant", content: "你好" } },
    );
    await store.getState().sendMessage("hi");
    const roles = store.getState().messages.map((m) => m.role);
    expect(roles).toContain("user");
    expect(roles).toContain("assistant");
    expect(store.getState().busy).toBe(false);
    expect(store.getState().streamingText).toBe("");
  });

  it("没有选中对话时不发消息", async () => {
    await store.getState().sendMessage("hi");
    expect(store.getState().messages).toHaveLength(0);
  });
});
