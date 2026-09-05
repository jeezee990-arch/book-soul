import { useEffect, useState } from "react";
import { Play, Sparkles, FileText } from "lucide-react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import LoadingSkeleton from "@/components/layout/LoadingSkeleton";
import ErrorState from "@/components/layout/ErrorState";
import EmptyState from "@/components/layout/EmptyState";
import { skillsApi, type SkillSummary, type SkillRunResult } from "@/api/skills";
import { ApiError } from "@/api";
import { cn } from "@/lib/utils";

/** Skills 市场（Phase 6.4 + 7.2 雏形）：
 * - 列出已注册 skill
 * - 点 skill 卡片展开 → 输入字段 → 执行 → 看结果
 */
export default function Skills() {
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedName, setExpandedName] = useState<string | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SkillRunResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    skillsApi
      .list()
      .then((data) => {
        if (!cancelled) setSkills(data);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRun(skill: SkillSummary) {
    setRunning(true);
    setResult(null);
    try {
      // 简单按 schema 转换：string 类型用 inputs，其余跳过
      const payload: Record<string, unknown> = {};
      const props = skill.input_schema.properties ?? {};
      for (const [k, def] of Object.entries(props)) {
        const type = (def as { type?: string }).type;
        const v = inputs[k];
        if (v === undefined || v === "") continue;
        if (type === "integer" || type === "number") {
          payload[k] = Number(v);
        } else if (type === "array") {
          // 逗号分隔
          payload[k] = v.split(",").map((s) => s.trim()).filter(Boolean);
        } else {
          payload[k] = v;
        }
      }
      const r = await skillsApi.run(skill.name, payload);
      setResult(r);
      if (r.success) {
        toast.success(`${skill.name} 执行成功`);
      } else {
        toast.error(`${skill.name} 失败`, { description: r.error ?? undefined });
      }
    } catch (e: unknown) {
      const msg = e instanceof ApiError ? e.message : String(e);
      toast.error("执行失败", { description: msg });
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Skills</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          文本处理工具 · 字符统计 · 敏感词检测 · 后续可扩展（自动摘要 / 一致性 / 节奏分析）
        </p>
      </header>

      {error && <ErrorState message={error} />}
      {loading && <LoadingSkeleton rows={3} height={120} />}

      {!loading && !error && skills.length === 0 && (
        <EmptyState
          icon="🧩"
          title="还没有 skill"
          description="后端 builtin skill 应自动注册；如果为空请检查服务端"
        />
      )}

      {!loading && !error && skills.length > 0 && (
        <div className="space-y-3">
          {skills.map((s) => {
            const open = expandedName === s.name;
            const props = s.input_schema.properties ?? {};
            const required = s.input_schema.required ?? [];
            return (
              <Card key={s.name}>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <div className="space-y-1">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Sparkles className="h-3.5 w-3.5 text-neutral-400" />
                        {s.name}
                        {s.requires_llm && (
                          <span className="rounded bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-200 px-1.5 py-0.5 text-[10px]">
                            需 LLM
                          </span>
                        )}
                      </CardTitle>
                      <CardDescription>{s.description}</CardDescription>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setExpandedName(open ? null : s.name);
                        setResult(null);
                        setInputs({});
                      }}
                    >
                      {open ? "收起" : "使用"}
                    </Button>
                  </div>
                </CardHeader>

                {open && (
                  <CardContent className="space-y-3 pt-0 border-t border-neutral-200 dark:border-neutral-800">
                    <div className="space-y-2">
                      {Object.entries(props).map(([key, def]) => {
                        const type = (def as { type?: string; description?: string }).type;
                        const desc = (def as { description?: string }).description;
                        const isRequired = required.includes(key);
                        return (
                          <div key={key} className="space-y-1">
                            <label
                              className={cn(
                                "text-xs",
                                isRequired ? "text-neutral-700 dark:text-neutral-300" : "text-neutral-500",
                              )}
                            >
                              {key}
                              <span className="ml-1 text-[10px] text-neutral-400">
                                ({type ?? "string"}
                                {isRequired ? " · 必填" : ""})
                              </span>
                            </label>
                            {type === "string" && key === "text" ? (
                              <Textarea
                                value={inputs[key] ?? ""}
                                onChange={(e) =>
                                  setInputs((p) => ({ ...p, [key]: e.target.value }))
                                }
                                placeholder={desc ?? ""}
                                rows={4}
                              />
                            ) : (
                              <Input
                                value={inputs[key] ?? ""}
                                onChange={(e) =>
                                  setInputs((p) => ({ ...p, [key]: e.target.value }))
                                }
                                placeholder={desc ?? ""}
                              />
                            )}
                            {desc && (
                              <p className="text-[10px] text-neutral-500">{desc}</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleRun(s)}
                        disabled={running}
                      >
                        <Play className="mr-1.5 h-3 w-3" />
                        {running ? "执行中…" : "执行"}
                      </Button>
                    </div>

                    {result && (
                      <div className="mt-3 space-y-1">
                        <h4 className="text-xs font-medium text-neutral-500 flex items-center gap-1">
                          <FileText className="h-3 w-3" />
                          执行结果
                        </h4>
                        <pre
                          className={cn(
                            "text-xs font-mono whitespace-pre-wrap rounded-md p-3 max-h-80 overflow-auto",
                            result.success
                              ? "bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800"
                              : "bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800",
                          )}
                        >
                          {JSON.stringify(result, null, 2)}
                        </pre>
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}
