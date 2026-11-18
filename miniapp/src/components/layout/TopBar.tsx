import { topBarPaddingTop } from "@app/lib/layout";
import { cn } from "@app/lib/utils";
import type { ReactNode } from "react";

export interface TopBarProps {
  leading: ReactNode;
  title: string;
  trailing?: ReactNode;
  insetTop: number;
  className?: string;
  /**
   * Renders as a transparent overlay above the screen's own content instead
   * of pushing it down — for a screen whose background (e.g. a map) must
   * extend under the status bar and this bar, matching up-miniapps-by-night
   * and up-miniapps-explore's floating header row over a fullscreen map.
   * The row itself stays click-through (`pointer-events-none`) outside its
   * actual content so the screen behind remains interactive; `leading` and
   * `trailing` get their own `pointer-events-auto` back. The title gets a
   * small backdrop so it stays legible over arbitrary map imagery.
   */
  floating?: boolean;
}

// The top inset is applied here (not on the root) so this bar is the only
// place that reserves space for the status bar. See topBarPaddingTop. This
// is already the "padding on the bar that owns the edge, not a gap on the
// root" pattern (see AppShell's and BottomNav's comments) — TopBar has no
// background class today, so there's no visible seam yet, but if one is
// added later it will correctly extend under the status bar for free.
export function TopBar({
  className,
  floating = false,
  insetTop,
  leading,
  title,
  trailing,
}: TopBarProps) {
  return (
    <header
      className={cn(
        "flex shrink-0 items-center gap-3 px-4 pb-3",
        floating && "pointer-events-none fixed inset-x-0 top-0 z-30",
        className,
      )}
      style={{ paddingTop: topBarPaddingTop(insetTop) }}
    >
      <span className={cn(floating && "pointer-events-auto")}>{leading}</span>
      <h2
        className={cn(
          "min-w-0 flex-1 truncate text-sm-plus font-medium text-ink-soft",
          floating && "rounded-xl bg-black/50 px-3 py-1.5 backdrop-blur-sm",
        )}
      >
        {title}
      </h2>
      {trailing ? (
        <span className={cn(floating && "pointer-events-auto")}>
          {trailing}
        </span>
      ) : null}
    </header>
  );
}
