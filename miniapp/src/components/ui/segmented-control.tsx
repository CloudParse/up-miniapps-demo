import { Button } from "@app/components/ui/button";
import { cn } from "@app/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedControlProps<T extends string> {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function SegmentedControl<T extends string>({
  className,
  onChange,
  options,
  value,
}: SegmentedControlProps<T>) {
  return (
    <fieldset
      aria-label="Choix"
      className={cn(
        "flex gap-1 rounded-2xl bg-brand-card p-1 border border-brand-border",
        className,
      )}
    >
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <Button
            aria-pressed={isActive}
            className={cn("flex-1", !isActive && "text-ink-faint")}
            key={option.value}
            onClick={() => onChange(option.value)}
            size="sm"
            variant={isActive ? "primary" : "ghost"}
          >
            {option.label}
          </Button>
        );
      })}
    </fieldset>
  );
}
