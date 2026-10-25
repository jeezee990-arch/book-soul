/**
 * 聊天页（2026-10-25 新增）。
 *
 * 对应需求：「开设一个新的聊天界面，可以与云端模型聊天探讨想法，
 * 需要有多窗口以及项目管理模块」。
 *
 * 布局：左侧项目栏（可折叠）+ 右侧对话区。
 * 流式回复走 NDJSON，前端直连后端（不经过 Rust）。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, PanelLeftClose, PanelLeftOpen, Send, Square } from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "@/stores/chat-store";
import ProjectPanel from "./project-panel";
import MaterialPicker from "./material-picker";
import { cn } from "@/lib/utils";

export default function Chat() {
  const projects = useChatStore((s) => s.projects);
  const conversations = useChatStore((s) => s.conversations);
  const messages = useChatStore((s) => s.messages);
  const currentProjectId = useChatStore((s) => s.currentProjectId);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const panelOpen = useChatStore((s) => s.panelOpen);
  const setPanelOpen = useChatStore((s) => s.setPanelOpen);
  const streamingText = useChatStore((s) => s.streamingText);
  const streamingThinking = useChatStore((s) => s.streamingThinking);
  const busy = useChatStore((s) => s.busy);
  const loadProjects = useChatStore((s) => s.loadProjects);
  const selectProject = useChatStore((s) => s.selectProject);
  const createConversation = useChatStore((s) => s.createConversation);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stopStreaming = useChatStore((s) => s.stopStreaming);
  const setMaterials = useChatStore((s) => s.setMaterials);

  const [input, setInput] = useState("");
  const [pickerProjectId, setPickerProjectId] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // 首次进入：拉项目列表；恢复了上次选中的项目就接着加载
  useEffect(() => {
    void loadProjects().then(() => {
      const id = useChatStore.getState().currentProjectId;
      if (id) void selectProject(id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 新消息 → 滚到底
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, streamingText]);

  const currentProject = projects.find((p) => p.id === currentProjectId) ?? null;
  const currentConversation =
    conversations.find((c) => c.id === currentConversationId) ?? null;

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    if (currentConversationId === null) {
      toast.error("先选一个对话", { description: "在左边点「新建对话」" });
      return;
    }
    setInput("");
    try {
      await sendMessage(text);
    } catch (e: unknown) {
      toast.error("聊天失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  }, [input, busy, currentConversationId, sendMessage]);

  const pickerProject = projects.find((p) => p.id === pickerProjectId) ?? null;

  return (
    <div className="flex h-full min-h-0">
      {panelOpen ? (
        <ProjectPanel onPickMaterials={(id) => setPickerProjectId(id)} />
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* ===== 顶栏 ===== */}
        <div className="flex h-[46px] shrink-0 items-center gap-2 border-b border-neutral-200 px-3.5 dark:border-neutral-800">
          <button
            type="button"
            onClick={() => setPanelOpen(!panelOpen)}
            title={panelOpen ? "收起项目栏" : "展开项目栏"}
            className="grid h-7 w-7 place-items-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
          >
            {panelOpen ? (
              <PanelLeftClose className="h-4 w-4" />
            ) : (
              <PanelLeftOpen className="h-4 w-4" />
            )}
          </button>

          <div className="min-w-0">
            <span className="block truncate text-[12.5px] font-semibold">
              {currentProject ? currentProject.name : "聊天"}
            </span>
            {currentConversation ? (
              <span className="block truncate text-[11px] text-neutral-400">
                {currentConversation.title}
              </span>
            ) : null}
          </div>

          {currentProject && currentProject.materials.length > 0 ? (
            <span
              className="ml-1 rounded bg-violet-500/15 px-1.5 py-0.5 text-[10.5px] text-violet-400"
              title={`已接入 ${currentProject.materials.length} 项素材`}
            >
              {currentProject.materials.length} 项素材
            </span>
          ) : null}

          <div className="flex-1" />

          {currentProject ? (
            <button
              type="button"
              onClick={() =>
                void createConversation(currentProject.id).then(() =>
                  toast.success("已新建对话"),
                )
              }
              className="h-7 rounded-lg border border-neutral-200 px-2.5 text-[11.5px] text-neutral-600 transition-colors hover:bg-neutral-100 dark:border-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              新建对话
            </button>
          ) : null}
        </div>

        {/* ===== 消息区 ===== */}
        <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {!currentProject ? (
            <div className="mx-auto max-w-[520px] pt-16 text-center">
              <p className="text-[14px] font-semibold">和模型聊聊你的想法</p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-neutral-400">
                左边建一个项目，项目里可以开多个对话。
                <br />
                项目还能接入素材库里的设定，模型讨论时就知道你的底牌。
              </p>
            </div>
          ) : messages.length === 0 && !busy ? (
            <div className="mx-auto max-w-[520px] pt-16 text-center">
              <p className="text-[14px] font-semibold">
                {currentConversation ? currentConversation.title : "还没选对话"}
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-neutral-400">
                {currentConversation
                  ? "说说你在纠结什么：人物动机、剧情走向、章节节奏都行。"
                  : "在左边点「新建对话」开始。"}
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-[720px] space-y-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "flex flex-col",
                    m.role === "user" ? "items-end" : "items-start",
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13px] leading-[1.75]",
                      m.role === "user"
                        ? "bg-indigo-600 text-white"
                        : "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200",
                    )}
                  >
                    {m.content}
                  </div>
                </div>
              ))}

              {/* 流式中的助手回复 */}
              {busy || streamingText ? (
                <div className="flex flex-col items-start">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-neutral-100 px-3.5 py-2.5 text-[13px] leading-[1.75] text-neutral-700 dark:bg-neutral-800 dark:text-neutral-200">
                    {streamingThinking && !streamingText ? (
                      <span className="text-neutral-400">
                        {streamingThinking.slice(-50).trim()}
                        <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
                      </span>
                    ) : (
                      <>
                        {streamingText}
                        <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 bg-violet-500 align-middle" />
                      </>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* ===== 输入框 ===== */}
        <div className="shrink-0 border-t border-neutral-200 px-4 py-3 dark:border-neutral-800">
          <div className="mx-auto flex max-w-[720px] items-end gap-2 rounded-xl border border-neutral-200 bg-white px-3 py-2 focus-within:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:focus-within:border-neutral-700">
            <textarea
              value={input}
              rows={1}
              disabled={!currentConversation}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder={
                currentConversation
                  ? "说说你的想法…（Enter 发送，Shift+Enter 换行）"
                  : "先在左边新建或选择一个对话"
              }
              className="max-h-[160px] min-h-[24px] flex-1 resize-none bg-transparent py-1 text-[13px] leading-relaxed outline-none placeholder:text-neutral-400 disabled:opacity-50"
            />
            {busy ? (
              <button
                type="button"
                onClick={stopStreaming}
                title="停止"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-neutral-200 text-neutral-600 transition-colors hover:bg-neutral-300 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700"
              >
                <Square className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim() || !currentConversation}
                title="发送"
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-indigo-600 text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      <MaterialPicker
        open={pickerProjectId !== null}
        selected={pickerProject?.materials ?? []}
        onClose={() => setPickerProjectId(null)}
        onSave={async (ids) => {
          if (pickerProjectId !== null) {
            await setMaterials(pickerProjectId, ids);
            toast.success(`已接入 ${ids.length} 项素材`);
          }
        }}
      />
    </div>
  );
}
