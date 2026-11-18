import type { IEdgeInsets } from "@cloudparse/up-miniapps-sdk";
import type { ReactNode } from "react";

export interface AppShellProps {
  insets: IEdgeInsets;
  children: ReactNode;
}

// Root layout. Left and right insets are applied here. Top and bottom are
// each reserved by the bar that owns that edge (TopBar, BottomNav) instead
// of here: a bar's own background needs to extend into its inset — behind
// the (transparent) status/nav bar — so the bar's own color shows there,
// not AppShell's. Padding here instead would leave AppShell's background
// showing through that gap, a visible seam against a differently-colored
// bar. See BottomNav's own paddingBottom for the matching bottom fix.
//
// `h-full`, never `h-dvh`/`h-screen`/a viewport unit: this app renders
// `edgeToEdge` in the SDK's phone simulator (see App.tsx's <SDKProvider>),
// where the real mount box is a `position: fixed` element sized to the
// (possibly scaled) phone screen, not the browser tab. A viewport unit
// ignores that box entirely and measures the actual browser viewport
// instead, which silently breaks sizing and makes insets look wrong.
// `h-full` correctly inherits whatever real pixel height the mount box
// has — in the simulator and on a real device's edge-to-edge WebView
// alike (see `html, body, #root { height: 100% }` in styles/index.css).
export function AppShell({ children, insets }: AppShellProps) {
  return (
    <div
      className="flex h-full flex-col overflow-hidden bg-brand-bg text-ink-bright"
      style={{
        paddingLeft: insets.left,
        paddingRight: insets.right,
      }}
    >
      {children}
    </div>
  );
}
