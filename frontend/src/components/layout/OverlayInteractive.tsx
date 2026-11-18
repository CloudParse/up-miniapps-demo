import { cn } from "@app/lib/utils";
import type { ReactNode } from "react";

// Wraps a card floated over a fullscreen map. The map's own overlay region
// is `pointer-events-none` so the map stays draggable through the gaps
// between cards; this re-enables pointer events for the card itself.
export function OverlayInteractive({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("pointer-events-auto", className)}>{children}</div>;
}
