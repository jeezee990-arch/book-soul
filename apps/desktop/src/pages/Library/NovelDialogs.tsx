/**
 * 作品重命名 / 删除确认对话框（2026-10-30）。
 *
 * 用项目已有的 `components/ui/dialog`（shadcn），
 * **不用 `window.prompt`** —— prompt 在 Tauri 里样式突兀、没法做校验、还阻塞 UI 线程。
 *
 * ⚠️ 与素材（灵感）重命名不同的两点：
 * 1. 作品名**不能为空**（后端 `_NAME_MAX` 200 字，且 name 必填），
 *    所以这里取消就返回 null（不改数据），空串直接禁用保存；
 * 2. 删除作品会**级联删掉**它的章节 / 人物卡 / 大纲 —— 确认框必须说清楚。
 */

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** 作品名最大长度（与后端 `_NAME_MAX` 一致）。 */
const NAME_MAX = 200;

interface RenameProps {
  open: boolean;
  /** 当前作品名（用于回填）。 */
  initialName: string;
  /**
   * 提交。
   *
   * 传 `null` 表示**用户取消**（不改动任何数据）；
   * 其它值表示要保存的新名字。
   */
  onSubmit: (name: string | null) => void;
}

/**
 * 作品重命名对话框。
 *
 * @param props - 组件属性
 */
export function NovelRenameDialog({
  open,
  initialName,
  onSubmit,
}: RenameProps) {
  const [value, setValue] = useState(initialName);

  // 每次打开时回填当前名字
  useEffect(() => {
    if (open) setValue(initialName);
  }, [open, initialName]);

  const trimmed = value.trim();
  const tooLong = value.length > NAME_MAX;
  const empty = trimmed.length === 0;

  return (
    // ⚠️ 关闭（ESC / 点遮罩）必须走 `onSubmit(null)`：
    //    不能走 `onSubmit("")` —— 作品名不能为空，
    //    传空串等于"把名字清掉"，后端会 422，用户还以为改名成功了。
    <Dialog open={open} onOpenChange={(o) => !o && onSubmit(null)}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-[15px]">重命名作品</DialogTitle>
          <DialogDescription className="text-[12px]">
            素材库里不能有两本同名作品。
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          value={value}
          maxLength={NAME_MAX}
          placeholder="输入作品名…"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !tooLong && !empty) onSubmit(trimmed);
          }}
        />
        {tooLong ? (
          <p className="text-[11.5px] text-rose-500">名称不能超过 {NAME_MAX} 字</p>
        ) : null}
        {empty ? (
          <p className="text-[11.5px] text-rose-500">名称不能为空</p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onSubmit(null)}>
            取消
          </Button>
          <Button
            size="sm"
            disabled={tooLong || empty}
            onClick={() => onSubmit(trimmed)}
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface ConfirmProps {
  open: boolean;
  /** 标题文字。 */
  title: string;
  /** 说明文字。 */
  description: string;
  /** 确认按钮文字。 */
  confirmLabel?: string;
  /** 确认回调。 */
  onConfirm: () => void;
  /** 取消回调。 */
  onCancel: () => void;
}

/**
 * 二次确认对话框（删除作品）。
 *
 * @param props - 组件属性
 */
export function NovelConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "删除",
  onConfirm,
  onCancel,
}: ConfirmProps) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-[15px]">{title}</DialogTitle>
          <DialogDescription className="text-[12px]">{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onCancel}>
            取消
          </Button>
          <Button
            size="sm"
            className="bg-rose-600 hover:bg-rose-700"
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
