import { cn } from "@app/lib/utils";

export interface SkeletonBlockProps {
  className?: string;
}

export function SkeletonBlock({ className }: SkeletonBlockProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-2xl bg-brand-card-strong",
        className,
      )}
    />
  );
}
