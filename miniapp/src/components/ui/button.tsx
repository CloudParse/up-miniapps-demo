import { cn } from "@app/lib/utils";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ButtonHTMLAttributes } from "react";

// Mini-apps run in a touch-only WebView: no hover, focus or active variants.
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl font-medium transition-opacity disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    defaultVariants: { size: "default", variant: "primary" },
    variants: {
      size: {
        default: "h-11 px-5 text-sm-plus",
        icon: "h-11 w-11",
        sm: "h-9 rounded-xl px-3 text-xs-plus",
      },
      variant: {
        danger: "bg-accent-danger text-ink-on-accent",
        ghost: "bg-transparent text-ink-soft",
        outline: "border border-brand-border bg-transparent text-ink-bright",
        primary: "bg-accent-primary text-ink-on-accent",
        secondary: "bg-brand-card-strong text-ink-bright",
      },
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({
  asChild = false,
  className,
  size,
  variant,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      className={cn(buttonVariants({ className, size, variant }))}
      type={asChild ? undefined : "button"}
      {...props}
    />
  );
}
