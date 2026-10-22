import { Button } from "@app/components/ui/button";
import { CloudOff } from "lucide-react";

export interface GreetingErrorProps {
  message: string;
  onRetry: () => void;
}

export function GreetingError({ message, onRetry }: GreetingErrorProps) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-danger/15 text-accent-danger">
        <CloudOff size={22} />
      </div>
      <div>
        <p className="font-display text-md-plus font-semibold">
          Backend unreachable
        </p>
        <p className="mt-1 text-sm-plus text-ink-soft">{message}</p>
      </div>
      <Button onClick={onRetry} variant="secondary">
        Try again
      </Button>
    </div>
  );
}
