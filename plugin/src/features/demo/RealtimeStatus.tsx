import { Badge, type BadgeProps } from "@cloudparse/up-backoffice-sdk";
import type { Realtime } from "@plugin/hooks/useRealtime";
import type { RealtimeStatus as Status } from "@plugin/lib/realtimeClient";

const LABEL: Record<Status, string> = {
  connecting: "connecting",
  offline: "offline",
  open: "connected",
  reconnecting: "reconnecting",
};

const VARIANT: Record<Status, BadgeProps["variant"]> = {
  connecting: "warning",
  offline: "error",
  open: "success",
  reconnecting: "warning",
};

// The state of the WebSocket, always visible: the developer sees that the page is live.
export function RealtimeStatus({ realtime }: { realtime: Realtime }) {
  return (
    <div className="space-y-1" data-testid="realtime-status">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={VARIANT[realtime.status]}>
          Realtime: {LABEL[realtime.status]}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {realtime.lastEventAt
            ? `${realtime.eventCount} event(s), last at ${realtime.lastEventAt.toLocaleTimeString("en-GB")}`
            : "No event yet."}
        </span>
      </div>
      {realtime.log.map((entry) => (
        <p className="break-all text-xs text-muted-foreground" key={entry.id}>
          {entry.text}
        </p>
      ))}
    </div>
  );
}
