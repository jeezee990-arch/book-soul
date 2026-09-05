import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import EmptyState from "@/components/layout/EmptyState";
import type { Novel } from "@/lib/types";

interface Props {
  novels: Novel[];
  value: number | null;
  onChange: (id: number) => void;
  loading: boolean;
}

/** 作品下拉选择器（Phase 4.1 抽组件）。 */
export default function NovelSelector({ novels, value, onChange, loading }: Props) {
  if (!loading && novels.length === 0) {
    return (
      <EmptyState
        icon="📚"
        title="还没有作品"
        description="先去灵感园创建，或在作品库导入本地小说。"
      />
    );
  }

  return (
    <Select
      value={value !== null ? String(value) : undefined}
      onValueChange={(v) => onChange(Number(v))}
      disabled={loading || novels.length === 0}
    >
      <SelectTrigger className="w-72">
        <SelectValue placeholder="选择作品" />
      </SelectTrigger>
      <SelectContent>
        {novels.map((n) => (
          <SelectItem key={n.id} value={String(n.id)}>
            <span className="font-medium">{n.name}</span>
            <span className="ml-2 text-xs text-neutral-400">· {n.genre}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
