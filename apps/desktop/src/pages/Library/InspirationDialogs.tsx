/**
 * 素材重命名 / 删除确认对话框（2026-10-29）。
 *
 * 用项目已有的 `components/ui/dialog`（shadcn），
 * **不用 `window.prompt`** —— prompt 在 Tauri 里样式突兀、没法做校验、还阻塞 UI 线程。
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

/** 标题最大长度（与后端 `_TITLE_MAX` 一致）。 */
const TITLE_MAX = 200;

interface RenameProps {
  open: boolean;
  /** 当前的标题（用于回填；空串表示还没命名过）。 */
  initialTitle: string;
  /**
   * 提交。
   *
   * 传 `null` 表示**用户取消**（不改动任何数据）；
   * 传空串表示"保存但清空标题"（回落到自动摘要）。
   */
  onSubmit: (title: string | null) => void;
}

/**
 * 重命名对话框。
 *
 * @param props - 组件属性
 */
export function InspirationRenameDialog({
  open,
  initialTitle,
  onSubmit,
}: RenameProps) {
  const [value, setValue] = useState(initialTitle);

  // 每次打开时回填当前标题
  useEffect(() => {
    if (open) setValue(initialTitle);
  }, [open, initialTitle]);

  const trimmed = value.trim();
  const tooLong = value.length > TITLE_MAX;

  return (
    // ⚠️ 2026-10-29 评审：关闭（ESC / 点遮罩）必须走 `onSubmit(null)`，
    //    不能走 `onSubmit("")` —— 后者等于"保存空标题"，
    //    会把用户自定义的标题**静默清空**（点取消反而丢数据）。
    <Dialog open={open} onOpenChange={(o) => !o && onSubmit(null)}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-[15px]">重命名素材</DialogTitle>
          <DialogDescription className="text-[12px]">
            留空则使用自动摘要作为显示名。
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          value={value}
          maxLength={TITLE_MAX}
          placeholder="输入显示名…"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !tooLong) onSubmit(trimmed);
          }}
        />
        {tooLong ? (
          <p className="text-[11.5px] text-rose-500">标题不能超过 {TITLE_MAX} 字</p>
        ) : null}
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onSubmit(null)}>
            取消
          </Button>
          <Button size="sm" disabled={tooLong} onClick={() => onSubmit(trimmed)}>
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
 * 二次确认对话框（删除 / 批量删除）。
 *
 * @param props - 组件属性
 */
export function InspirationConfirmDialog({
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
