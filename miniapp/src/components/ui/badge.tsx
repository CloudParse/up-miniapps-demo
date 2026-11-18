import { cn } from "@app/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs-plus font-medium",
  {
    defaultVariants: { tone: "neutral" },
    variants: {
      tone: {
        danger: "bg-accent-danger/15 text-accent-danger",
        neutral: "bg-brand-card-strong text-ink-soft",
        primary: "bg-accent-primary/15 text-accent-primary",
        success: "bg-accent-success/15 text-accent-success",
        warning: "bg-accent-warning/15 text-accent-warning",
      },
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
