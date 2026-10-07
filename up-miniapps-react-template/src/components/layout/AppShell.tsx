import { AuroraBackground } from "@app/components/layout/AuroraBackground";
import type { IEdgeInsets } from "@cloudparse/up-miniapps-sdk";
import type { ReactNode } from "react";

export interface AppShellProps {
  insets: IEdgeInsets;
  children: ReactNode;
}

// Root layout. Only the left and right insets are applied here: the top bar
// and any bottom bar reserve their own edge so their background can extend
// under the (transparent) status bar. `h-full`, never a viewport unit: see
// styles/index.css.
export function AppShell({ children, insets }: AppShellProps) {
  return (
    <div
      className="relative flex h-full flex-col overflow-hidden bg-brand-bg font-sans text-ink-bright"
      style={{ paddingLeft: insets.left, paddingRight: insets.right }}
    >
      <AuroraBackground />
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        {children}
      </div>
    </div>
  );
}
