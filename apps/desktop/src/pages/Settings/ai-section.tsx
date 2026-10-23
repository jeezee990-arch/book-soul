/**
 * 设置 · AI 增强分区（原「Skills」一级页面降级至此）。
 *
 * 旧 Skills 页是**开发者视角**：展示"内置 / 已预装 / 后处理 / 需 LLM"
 * 这类实现细节，而普通作者只想知道"AI 会不会自动帮我做敏感词检查、字数统计"。
 *
 * 现在：
 * - 默认只显示**作者视角**（中文名 + 一句话说明 + 开关）
 * - 高级信息（触发场景 / 来源 / 类型）折叠在下面
 */

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { skillsApi, type SkillStatus } from "@/api/skills";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** skill 技术名 → 作者能看懂的名字。 */
const DISPLAY_NAME: Record<string, string> = {
  word_counter: "字数统计",
  sensitive_word: "敏感词检查",
  chapter_summarizer: "章节摘要",
  character_extractor: "角色抽取",
  plot_analyzer: "剧情分析",
  web_search: "联网搜索",
  read_local_file: "读取本地文件",
  consistency_checker: "一致性检查",
  style_analyzer: "文风分析",
  pacing_visualizer: "节奏分析",
  outline_structurer: "大纲结构化",
  genre_classifier: "题材识别",
};

/** 作者视角的一句话说明。 */
const DISPLAY_DESC: Record<string, string> = {
  word_counter: "自动统计章节字数，并按目标字数裁剪或补足",
  sensitive_word: "自动拦截违禁词，生成时静默替换",
  chapter_summarizer: "自动生成前几章摘要，供后续章节引用",
  character_extractor: "从大纲里自动抽出角色，生成人物卡",
  plot_analyzer: "分析剧情结构，帮你理清主线与支线",
  web_search: "生成时允许联网查资料",
  read_local_file: "允许 AI 读取你指定的本地资料",
  consistency_checker: "比对人物卡与正文，标记不一致处",
  style_analyzer: "学习全书句式风格，注入到生成 prompt",
  pacing_visualizer: "分析章节节奏，指出拖沓或过急",
  outline_structurer: "把自由描述整理成卷 → 章结构",
  genre_classifier: "识别文本题材，自动套用对应常识",
};

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

function applyTypeLabel(t: string): string {
  if (t === "post_process") return "生成后处理";
  if (t === "pre_process") return "生成前处理";
  if (t === "both") return "前后都处理";
  return t;
}

export default function AiSection() {
  const [skills, setSkills] = useState<SkillStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setSkills(await skillsApi.list());
    } catch (e: unknown) {
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
        toast.success(`${DISPLAY_NAME[name] ?? name} 已${currentEnabled ? "关闭" : "开启"}`, {
          description: currentEnabled
            ? "后续生成不再经过这个能力"
            : "后续生成会自动经过这个能力",
        });
      } catch (e: unknown) {
        toast.error("切换失败", {
          description: e instanceof Error ? e.message : String(e),
        });
      } finally {
        setToggling(null);
      }
    },
    [],
  );

  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <div>
      <h3 className="text-[14px] font-semibold">AI 增强</h3>
      <p className="mt-0.5 mb-4 text-[11.5px] leading-relaxed text-neutral-400">
        这些能力会自动介入生成过程，不需要手动调用。关掉不影响主流程。
        {skills.length > 0 ? `（已开启 ${enabledCount} / ${skills.length}）` : ""}
      </p>

      {loading ? (
        <p className="text-[12px] text-neutral-400">加载中…</p>
      ) : skills.length === 0 ? (
        <div className="rounded-xl border border-dashed border-neutral-200 p-8 text-center dark:border-neutral-800">
          <p className="text-[12.5px] text-neutral-500">还没有可用的增强能力</p>
          <p className="mt-1.5 text-[11px] text-neutral-400">
            内置能力会自动加载；自定义能力请放到{" "}
            <code className="font-mono">data/skills/&lt;name&gt;/</code>
          </p>
        </div>
      ) : (
        <>
          <div className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {skills.map((s) => {
              const on = s.enabled;
              const name = DISPLAY_NAME[s.name] ?? s.name;
              const desc =
                DISPLAY_DESC[s.name] ?? s.description ?? "（无描述）";
              return (
                <div key={s.name} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-medium">{name}</div>
                    <div className="mt-0.5 text-[11px] leading-relaxed text-neutral-400">
                      {desc}
                    </div>
                    {showAdvanced ? (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <code className="font-mono text-[10px] text-neutral-400">
                          {s.name}
                        </code>
                        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[9.5px] text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                          {s.source === "user" ? "自定义" : "内置"}
                        </span>
                        <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-[9.5px] text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
                          {applyTypeLabel(s.apply_type)}
                        </span>
                        {s.requires_llm ? (
                          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[9.5px] text-amber-600 dark:text-amber-400">
                            需 LLM
                          </span>
                        ) : null}
                        {(s.triggers.length > 0 ? s.triggers : ["all"]).map(
                          (t) => (
                            <span
                              key={t}
                              className="rounded bg-neutral-100 px-1.5 py-0.5 text-[9.5px] text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400"
                            >
                              {SCENE_LABELS[t] ?? t}
                            </span>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                  <Switch
                    checked={on}
                    onCheckedChange={() => void toggle(s.name, on)}
                    disabled={toggling === s.name}
                    aria-label={`${name} 开关`}
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="inline-flex items-center gap-1 text-[11.5px] text-neutral-400 transition-colors hover:text-neutral-600 dark:hover:text-neutral-200"
            >
              <ChevronDown
                className={cn("h-3 w-3 transition-transform", showAdvanced && "rotate-180")}
              />
              {showAdvanced ? "收起高级信息" : "展开高级信息（技术名 / 来源 / 触发场景）"}
            </button>
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => void refresh()}
              disabled={loading}
            >
              <RefreshCw className={cn("mr-1.5 h-3 w-3", loading && "animate-spin")} />
              刷新
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
