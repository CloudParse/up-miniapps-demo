import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { type HapticStyleType, sdk } from "@cloudparse/up-miniapps-sdk";

const STYLES: readonly HapticStyleType[] = [
  "light",
  "medium",
  "heavy",
  "rigid",
  "soft",
  "success",
  "warning",
  "error",
];

export function HapticsDemo() {
  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Touche un style pour sentir la vibration."
        title="Haptique"
      />
      <div className="grid grid-cols-2 gap-3">
        {STYLES.map((style) => (
          <Button
            key={style}
            onClick={() => void sdk.haptic.trigger(style)}
            variant="secondary"
          >
            {style}
          </Button>
        ))}
      </div>
    </div>
  );
}
