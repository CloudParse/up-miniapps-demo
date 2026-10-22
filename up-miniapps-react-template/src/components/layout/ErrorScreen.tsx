import { ExitButton } from "@app/components/layout/ExitButton";
import { Button } from "@app/components/ui/button";
import { topBarPaddingTop } from "@app/lib/layout";
import { WifiOff } from "lucide-react";

export interface ErrorScreenProps {
  message: string;
  insetTop: number;
  onRetry: () => void;
  onExit: () => void;
}

// Boot failures always end here, with a retry and an exit path. Never a silent
// spinner. The exit button is fixed so it is not nested under any inset padding.
export function ErrorScreen({
  insetTop,
  message,
  onExit,
  onRetry,
}: ErrorScreenProps) {
  return (
    <div className="relative flex h-full flex-col items-center justify-center gap-5 bg-brand-bg px-8 text-center text-ink-bright">
      <div
        className="fixed inset-x-0 top-0 flex items-center px-4 pb-3"
        style={{ paddingTop: topBarPaddingTop(insetTop) }}
      >
        <ExitButton mode="exit" onPress={onExit} />
      </div>
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-accent-danger/15 text-accent-danger">
        <WifiOff size={30} />
      </div>
      <div>
        <p className="font-display text-md-plus font-semibold">
          Something went wrong
        </p>
        <p className="mt-2 max-w-sm text-sm-plus text-ink-soft">{message}</p>
      </div>
      <Button className="w-full max-w-xs" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
