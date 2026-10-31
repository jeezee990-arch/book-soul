/**
 * 步骤 1 · 书名输入（2026-10-30 新增）。
 *
 * 为什么要有它
 * ------------
 * 以前「开新书」全程不能命名，名字由后端自动生成（``修仙新作``）。
 * 后果有两个：
 *
 * 1. 素材库里一堆叫「修仙新作 / 修仙新作 2」的书，用户分不清；
 * 2. **自动名撞上已有作品时，新书根本存不进素材库** ——
 *    后端按名字 upsert，新书被合并进旧书，旧书的大纲还被冲掉。
 *
 * 现在：作者可以自己起名；留空则自动命名（后端保证唯一）。
 * 输入时如果和素材库里的书重名，**当场提示**会改成什么，
 * 别等生成完才发现名字变了。
 */

import { useMemo } from "react";
import { PenLine } from "lucide-react";
import { useNovelsStore } from "@/stores/novels-store";
import { duplicateHint } from "@/lib/novel-name";
import { Input } from "@/components/ui/input";

interface Props {
  /** 当前输入（留空 = 自动命名） */
  value: string;
  /** 输入变化 */
  onChange: (value: string) => void;
  /**
   * 要排除的名字。
   *
   * 同一向导内"重生成同一本"时，这本书自己的名字不算撞名。
   */
  excludeName?: string | null;
}

/** 书名最大长度（与后端 `_NAME_MAX` 一致）。 */
const NAME_MAX = 200;

export default function NovelNameField({ value, onChange, excludeName }: Props) {
  const novels = useNovelsStore((s) => s.novels);

  const names = useMemo(() => novels.map((n) => n.name), [novels]);
  const hint = useMemo(
    () => duplicateHint(value, names, excludeName),
    [value, names, excludeName],
  );

  return (
    <section className="mb-6">
      <div className="mb-2.5 flex items-baseline gap-2">
        <h3 className="text-[12.5px] font-semibold">书名</h3>
        <span className="text-[11.5px] text-neutral-400">
          留空则自动命名（撞名会自动加序号）
        </span>
      </div>
      <div className="relative">
        <PenLine className="absolute top-2.5 left-2.5 h-3.5 w-3.5 text-neutral-400" />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="例如：剑起青云"
          maxLength={NAME_MAX}
          className="h-9 pl-8 text-[13px]"
        />
      </div>
      {hint ? (
        <p className="mt-1.5 text-[11.5px] text-amber-600 dark:text-amber-400">
          {hint}
        </p>
      ) : null}
    </section>
  );
}
