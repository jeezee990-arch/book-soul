/**
 * 大纲规模设置（2026-10-25 新增）。
 *
 * 为什么要有这个控件
 * ------------------
 * 旧的大纲 prompt 把规模写死成"20-40 章"，作者写"全书 100 章"会被无视。
 * 现在规模是**显式参数**：这里让作者直接定死，后端写进 prompt 的硬性要求。
 *
 * 两个便利点：
 * 1. **自动识别**：想法词条里写了"共100章""每章3000字"会自动填进来；
 * 2. **即时换算**：改总章数就实时显示"共 N 卷 · 预计 M 万字"。
 *
 * ⚠️ 作者手动改过之后就不再自动覆盖（避免"我填的 50 章又被改回 100"）。
 */

import { RefreshCw } from "lucide-react";
import {
  formatTotalWords,
  normalizeScale,
  scaleTotalWords,
  scaleVolumeCount,
  type OutlineScale,
} from "@/lib/outline-scale";
import { cn } from "@/lib/utils";

interface Props {
  value: OutlineScale;
  onChange: (next: OutlineScale) => void;
  /** 想法里识别到了规模 → 显示「重新识别」按钮 */
  canRedetect?: boolean;
  disabled?: boolean;
}

interface FieldProps {
  label: string;
  suffix: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onChange: (v: number) => void;
}

function ScaleField({
  label,
  suffix,
  value,
  min,
  max,
  step = 1,
  disabled,
  onChange,
}: FieldProps) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[11px] text-neutral-400">{label}</span>
      <span className="flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-2 py-1 focus-within:border-indigo-400 dark:border-neutral-800 dark:bg-neutral-900">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          onChange={(e) => {
            const n = Number(e.target.value);
            if (!Number.isFinite(n)) return;
            onChange(Math.max(min, Math.min(max, Math.round(n))));
          }}
          className="w-full min-w-0 bg-transparent text-[13px] font-medium tabular-nums outline-none disabled:opacity-50"
        />
        <span className="shrink-0 text-[11px] text-neutral-400">{suffix}</span>
      </span>
    </label>
  );
}

export default function OutlineScaleBar({
  value,
  onChange,
  canRedetect,
  disabled,
}: Props) {
  const volumeCount = scaleVolumeCount(value);
  const totalWords = scaleTotalWords(value);

  const update = (patch: Partial<OutlineScale>) => {
    onChange(normalizeScale({ ...value, ...patch }));
  };

  return (
    <div className="rounded-xl border border-neutral-200 p-3.5 dark:border-neutral-800">
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h4 className="text-[12.5px] font-semibold">大纲规模</h4>
        {canRedetect ? (
          <span className="flex items-center gap-1 text-[11px] text-neutral-400">
            <RefreshCw className="h-3 w-3" />
            已按想法自动填充
          </span>
        ) : null}
      </div>

      <div className="flex gap-2.5">
        <ScaleField
          label="总章数"
          suffix="章"
          value={value.totalChapters}
          min={1}
          max={500}
          disabled={disabled}
          onChange={(v) => update({ totalChapters: v })}
        />
        <ScaleField
          label="每卷"
          suffix="章"
          value={value.chaptersPerVolume}
          min={1}
          max={100}
          disabled={disabled}
          onChange={(v) => update({ chaptersPerVolume: v })}
        />
        <ScaleField
          label="每章"
          suffix="字"
          value={value.wordsPerChapter}
          min={500}
          max={20000}
          step={100}
          disabled={disabled}
          onChange={(v) => update({ wordsPerChapter: v })}
        />
      </div>

      <p
        className={cn(
          "mt-2.5 text-[11.5px] text-neutral-400",
          volumeCount > 12 && "text-amber-500",
        )}
      >
        共 <b className="font-semibold text-neutral-600 dark:text-neutral-300">{volumeCount}</b> 卷
        · 预计{" "}
        <b className="font-semibold text-neutral-600 dark:text-neutral-300">
          {formatTotalWords(totalWords)}
        </b>
        {volumeCount > 12 ? (
          <span className="ml-1.5">（卷数较多，大纲会分批生成，耗时更长）</span>
        ) : null}
      </p>
    </div>
  );
}
