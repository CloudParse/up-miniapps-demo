import { topBarPaddingTop } from "@app/lib/layout";
import type { ReactNode } from "react";

export interface TopBarProps {
  leading: ReactNode;
  title: string;
  insetTop: number;
}

// The top inset is applied here, not on the root, so this bar is the only
// place that reserves space for the status bar. See topBarPaddingTop.
export function TopBar({ insetTop, leading, title }: TopBarProps) {
  return (
    <header
      className="flex shrink-0 items-center gap-3 px-4 pb-3"
      style={{ paddingTop: topBarPaddingTop(insetTop) }}
    >
      {leading}
      <h2 className="min-w-0 flex-1 truncate text-sm-plus font-medium text-ink-soft">
        {title}
      </h2>
    </header>
  );
}
