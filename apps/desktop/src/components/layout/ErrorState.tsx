/**
 * 错误状态组件（Phase 3.9）。
 *
 * 用途：API 错误 / 加载失败时显示。
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = "加载失败",
  message,
  onRetry,
}: Props) {
  return (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="text-base text-destructive">{title}</CardTitle>
        <CardDescription className="font-mono text-xs whitespace-pre-wrap break-all">
          {message}
        </CardDescription>
      </CardHeader>
      {onRetry && (
        <CardContent>
          <Button onClick={onRetry} variant="outline" size="sm">
            重试
          </Button>
        </CardContent>
      )}
    </Card>
  );
}
