import { cn } from "@app/lib/utils";
import { Switch as SwitchPrimitive } from "radix-ui";

export interface SwitchProps
  extends Omit<SwitchPrimitive.SwitchProps, "className"> {
  className?: string;
}

export function Switch({ className, ...props }: SwitchProps) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full bg-brand-border data-[state=checked]:bg-accent-primary",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-1 rounded-full bg-ink-bright transition-transform data-[state=checked]:translate-x-6 data-[state=checked]:bg-ink-on-accent" />
    </SwitchPrimitive.Root>
  );
}
