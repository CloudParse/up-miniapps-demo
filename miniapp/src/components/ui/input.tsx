import { cn } from "@app/lib/utils";
import type { InputHTMLAttributes } from "react";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-2xl border border-brand-border bg-brand-card px-4 text-sm-plus text-ink-bright placeholder:text-ink-faint",
        className,
      )}
      {...props}
    />
  );
}
