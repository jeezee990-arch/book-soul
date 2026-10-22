/** Skills 状态面板（Phase Skills 自动化）。
 *
 * 重新设计：skill **不再需要手动调用**——内置 / 预装到 ``data/skills/`` 后，
 * 业务代码（plot/outline/character/chapter 生成）会自动调用匹配的 skill。
 *
 * 这里只做：
 *  - 浏览所有已注册的 skill
 *  - 查看来源（内置 / 已预装）
 *  - 查看自动触发场景（按 manifest 的 ``triggers``）
 *  - 一键 enable / disable（停用某个 skill 后，下次 LLM 流式输出不会被它处理）
 *
 * 不再有"执行"按钮——用户装好 skill 即可，不用手动跑。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { skillsApi, type SkillStatus } from "@/api/skills";

const SCENE_LABELS: Record<string, string> = {
  all: "全部场景",
  "scene:plot_generation": "剧情生成",
  "scene:outline_generation": "大纲生成",
  "scene:character_generation": "人物卡生成",
  "scene:chapter_generation": "章节正文生成",
  "scene:chapter_rewrite": "章节重写",
  "scene:quality_check": "质量检测",
  "scene:summary": "摘要",
};

function formatTrigger(t: string): string {
  return SCENE_LABELS[t] ?? t;
}

function humanizeApplyType(name: string): string {
  if (name === "post_process") return "后处理";
  if (name === "pre_process") return "预处理";
  if (name === "both") return "前后均可";
  return name;
}

export default function Skills() {
  const [skills, setSkills] = useState<SkillStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await skillsApi.list();
      setSkills(list);
    } catch (e) {
      toast.error("加载 skills 失败", {
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const toggle = useCallback(
    async (name: string, currentEnabled: boolean) => {
      setToggling(name);
      try {
        const next = currentEnabled
          ? await skillsApi.disable(name)
          : await skillsApi.enable(name);
        setSkills((prev) => prev.map((s) => (s.name === name ? next : s)));
        toast.success(
          `${name} 已${currentEnabled ? "禁用" : "启用"}`,
          { description: currentEnabled ? "后续 LLM 输出不再经过此 skill" : "后续 LLM 输出将自动经过此 skill" },
        );
      } catch (e) {
        toast.error("切换失败", {
          description: e instanceof Error ? e.message : String(e),
        });
      } finally {
        setToggling(null);
      }
    },
    [],
  );

  const stats = useMemo(() => {
    const builtin = skills.filter((s) => s.source === "builtin").length;
    const user = skills.filter((s) => s.source === "user").length;
    const enabled = skills.filter((s) => s.enabled).length;
    const autoScenes = new Set<string>();
    for (const s of skills) {
      if (s.enabled) {
        for (const t of s.triggers) autoScenes.add(t);
      }
    }
    return { builtin, user, enabled, autoScenes: autoScenes.size };
  }, [skills]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">Skills</h2>
          <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
            skill 预装到 <code className="px-1 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800">data/skills/</code> 后会自动注入对应场景；无需手动调用
          </p>
        </div>
        <button
          onClick={refresh}
          className="text-xs px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-100 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors inline-flex items-center gap-1"
          disabled={loading}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
          >
            <path d="M21 12a9 9 0 11-3-6.7M21 3v6h-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          刷新
        </button>
      </header>

      {/* 概览卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="内置" value={stats.builtin} />
        <StatCard label="已预装" value={stats.user} />
        <StatCard label="已启用" value={stats.enabled} accent="green" />
        <StatCard label="自动调用场景" value={stats.autoScenes} accent="indigo" />
      </div>

      {loading ? (
        <p className="text-sm text-neutral-500">加载中…</p>
      ) : skills.length === 0 ? (
        <div className="rounded-xl border border-dashed border-neutral-200 dark:border-neutral-800 p-8 text-center text-neutral-500">
          <p className="text-sm">还没有 skill</p>
          <p className="text-xs mt-2">内置 skill 应自动加载；预装 skill 请放入 <code>data/skills/&lt;name&gt;/manifest.yaml</code> + <code>handler.py</code></p>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map((s) => (
            <SkillRow
              key={s.name}
              skill={s}
              toggling={toggling === s.name}
              onToggle={() => toggle(s.name, s.enabled)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: "green" | "indigo" }) {
  const color =
    accent === "green"
      ? "text-green-600 dark:text-green-400"
      : accent === "indigo"
        ? "text-indigo-600 dark:text-indigo-400"
        : "text-neutral-900 dark:text-neutral-100";
  return (
    <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 p-4">
      <p className="text-xs uppercase tracking-wider text-neutral-500">{label}</p>
      <p className={`text-2xl font-semibold mt-1 ${color}`}>{value}</p>
    </div>
  );
}

function SkillRow({
  skill,
  toggling,
  onToggle,
}: {
  skill: SkillStatus;
  toggling: boolean;
  onToggle: () => void;
}) {
  const isEnabled = skill.enabled;
  const triggers = skill.triggers.length > 0 ? skill.triggers : ["all"];
  return (
    <div
      className={`rounded-xl border p-4 transition-all ${
        isEnabled
          ? "border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
          : "border-neutral-200/50 dark:border-neutral-800/50 bg-neutral-50/50 dark:bg-neutral-900/30 opacity-60"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="font-mono text-sm font-medium">{skill.name}</code>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider ${
                skill.source === "user"
                  ? "bg-indigo-100 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300"
                  : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              }`}
            >
              {skill.source === "user" ? "已预装" : "内置"}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400">
              {humanizeApplyType(skill.apply_type)}
            </span>
            {skill.requires_llm && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                需 LLM
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1.5">
            {skill.description || "（无描述）"}
          </p>
          <div className="flex items-center gap-1.5 flex-wrap mt-2">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400">触发：</span>
            {triggers.map((t) => (
              <span
                key={t}
                className="text-[10px] px-1.5 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400"
              >
                {formatTrigger(t)}
              </span>
            ))}
          </div>
        </div>

        <button
          onClick={onToggle}
          disabled={toggling}
          className={`shrink-0 w-10 h-6 rounded-full relative transition-colors ${
            isEnabled ? "bg-indigo-500" : "bg-neutral-300 dark:bg-neutral-700"
          } ${toggling ? "opacity-50 cursor-not-allowed" : ""}`}
          aria-label={isEnabled ? "禁用" : "启用"}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
              isEnabled ? "translate-x-4" : ""
            }`}
          />
        </button>
      </div>
    </div>
  );
}