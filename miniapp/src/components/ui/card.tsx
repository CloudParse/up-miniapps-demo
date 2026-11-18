import { cn } from "@app/lib/utils";
import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  tone?: "default" | "strong";
}

export function Card({ className, tone = "default", ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-brand-border p-4",
        tone === "strong" ? "bg-brand-card-strong" : "bg-brand-card",
        className,
      )}
      {...props}
    />
  );
}
