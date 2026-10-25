/**
 * 聊天页左侧项目栏（2026-10-25 新增）。
 *
 * 对应需求：「进入聊天界面后从左侧弹出一个窗口栏（类似写作页的章节栏），
 * 可以新建项目，项目内可以新建对话，项目可以从素材库选择素材进行接入」。
 *
 * 层级：项目（可折叠）→ 对话。
 */

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FolderOpen,
  MessageSquarePlus,
  Paperclip,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";

export default function ProjectPanel({
  onPickMaterials,
}: {
  /** 打开素材选择器（带项目 id） */
  onPickMaterials: (projectId: number) => void;
}) {
  const projects = useChatStore((s) => s.projects);
  const conversations = useChatStore((s) => s.conversations);
  const currentProjectId = useChatStore((s) => s.currentProjectId);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const selectProject = useChatStore((s) => s.selectProject);
  const createProject = useChatStore((s) => s.createProject);
  const renameProject = useChatStore((s) => s.renameProject);
  const deleteProject = useChatStore((s) => s.deleteProject);
  const createConversation = useChatStore((s) => s.createConversation);
  const renameConversation = useChatStore((s) => s.renameConversation);
  const deleteConversation = useChatStore((s) => s.deleteConversation);
  const selectConversation = useChatStore((s) => s.selectConversation);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  /** 展开的项目 id 集合（默认全展开当前项目） */
  const [collapsed, setCollapsed] = useState<number[]>([]);

  const toggle = (id: number) => {
    setCollapsed((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const submitNewProject = async () => {
    const name = newName.trim();
    if (!name) return;
    setNewName("");
    setCreating(false);
    try {
      await createProject(name);
    } catch (e: unknown) {
      toast.error("新建项目失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const commitRename = async (kind: "project" | "conversation", id: number) => {
    const text = editText.trim();
    setEditingId(null);
    if (!text) return;
    try {
      if (kind === "project") await renameProject(id, text);
      else await renameConversation(id, text);
    } catch (e: unknown) {
      toast.error("重命名失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    }
  };

  return (
    <aside className="flex w-[244px] shrink-0 flex-col border-r border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <span className="text-[10.5px] font-semibold tracking-[0.07em] text-neutral-400 uppercase">
          项目 {projects.length > 0 ? `· ${projects.length}` : ""}
        </span>
        <button
          type="button"
          onClick={() => setCreating(true)}
          title="新建项目"
          aria-label="新建项目"
          className="grid h-6 w-6 place-items-center rounded-md text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-2.5">
        {creating ? (
          <div className="mb-1.5 px-1">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitNewProject();
                if (e.key === "Escape") {
                  setCreating(false);
                  setNewName("");
                }
              }}
              onBlur={() => void submitNewProject()}
              placeholder="项目名，回车确认"
              className="w-full rounded-lg border border-indigo-400 bg-white px-2 py-1.5 text-[12px] outline-none dark:bg-neutral-900"
            />
          </div>
        ) : null}

        {projects.length === 0 && !creating ? (
          <p className="px-2.5 py-4 text-center text-[11.5px] leading-relaxed text-neutral-400">
            还没有项目
            <br />
            点右上角 + 建一个
          </p>
        ) : null}

        {projects.map((project) => {
          const isCurrent = project.id === currentProjectId;
          const isCollapsed = collapsed.includes(project.id);
          const projectConversations = isCurrent ? conversations : [];
          return (
            <div key={project.id} className="mb-1">
              <div
                className={cn(
                  "group flex items-center gap-1 rounded-lg px-1.5 py-1 transition-colors",
                  isCurrent
                    ? "bg-indigo-500/10"
                    : "hover:bg-neutral-100 dark:hover:bg-neutral-800",
                )}
              >
                <button
                  type="button"
                  onClick={() => {
                    void selectProject(isCurrent ? null : project.id);
                    if (isCurrent) toggle(project.id);
                    else setCollapsed((prev) => prev.filter((x) => x !== project.id));
                  }}
                  className="flex min-w-0 flex-1 items-center gap-1 text-left"
                  title={project.name}
                >
                  {isCollapsed ? (
                    <ChevronRight className="h-3 w-3 shrink-0 text-neutral-400" />
                  ) : (
                    <ChevronDown className="h-3 w-3 shrink-0 text-neutral-400" />
                  )}
                  <FolderOpen className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
                  {editingId === project.id ? (
                    <input
                      autoFocus
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitRename("project", project.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      onBlur={() => void commitRename("project", project.id)}
                      className="min-w-0 flex-1 rounded border border-indigo-400 bg-white px-1 py-0.5 text-[12px] outline-none dark:bg-neutral-900"
                    />
                  ) : (
                    <span
                      className={cn(
                        "truncate text-[12.5px]",
                        isCurrent
                          ? "font-medium text-indigo-700 dark:text-indigo-300"
                          : "text-neutral-600 dark:text-neutral-400",
                      )}
                    >
                      {project.name}
                    </span>
                  )}
                </button>

                {project.materials.length > 0 ? (
                  <span
                    className="shrink-0 rounded bg-violet-500/15 px-1 text-[9.5px] text-violet-400"
                    title={`已接入 ${project.materials.length} 项素材`}
                  >
                    {project.materials.length}
                  </span>
                ) : null}

                <button
                  type="button"
                  onClick={() => onPickMaterials(project.id)}
                  title="接入素材"
                  className="hidden h-5 w-5 shrink-0 place-items-center rounded text-neutral-400 hover:bg-neutral-200/70 hover:text-neutral-700 group-hover:grid dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
                >
                  <Paperclip className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingId(project.id);
                    setEditText(project.name);
                  }}
                  title="重命名"
                  className="hidden h-5 w-5 shrink-0 place-items-center rounded text-neutral-400 hover:bg-neutral-200/70 hover:text-neutral-700 group-hover:grid dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
                >
                  <Pencil className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`删除项目「${project.name}」及其全部对话？`)) {
                      void deleteProject(project.id);
                    }
                  }}
                  title="删除项目"
                  className="hidden h-5 w-5 shrink-0 place-items-center rounded text-neutral-400 hover:bg-rose-500/15 hover:text-rose-500 group-hover:grid"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>

              {isCurrent && !isCollapsed ? (
                <div className="mt-0.5 mb-1 ml-3 border-l border-neutral-200 pl-1.5 dark:border-neutral-800">
                  {projectConversations.map((c) => {
                    const on = c.id === currentConversationId;
                    return (
                      <div
                        key={c.id}
                        className={cn(
                          "group flex items-center gap-1 rounded-lg px-1.5 py-1 transition-colors",
                          on
                            ? "bg-indigo-500/10"
                            : "hover:bg-neutral-100 dark:hover:bg-neutral-800",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => void selectConversation(c.id)}
                          className="min-w-0 flex-1 truncate text-left text-[12px]"
                          title={c.title}
                        >
                          {c.title}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(c.id);
                            setEditText(c.title);
                          }}
                          title="重命名"
                          className="hidden h-4 w-4 shrink-0 place-items-center rounded text-neutral-400 hover:text-neutral-700 group-hover:grid dark:hover:text-neutral-200"
                        >
                          <Pencil className="h-2.5 w-2.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (window.confirm(`删除对话「${c.title}」？`)) {
                              void deleteConversation(c.id);
                            }
                          }}
                          title="删除对话"
                          className="hidden h-4 w-4 shrink-0 place-items-center rounded text-neutral-400 hover:text-rose-500 group-hover:grid"
                        >
                          <Trash2 className="h-2.5 w-2.5" />
                        </button>
                      </div>
                    );
                  })}

                  <button
                    type="button"
                    onClick={() => void createConversation(project.id)}
                    className="flex w-full items-center gap-1 rounded-lg px-1.5 py-1 text-left text-[11.5px] text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
                  >
                    <MessageSquarePlus className="h-3 w-3" />
                    新建对话
                  </button>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
