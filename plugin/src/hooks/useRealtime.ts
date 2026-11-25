import { miniappApi, usePluginHost } from "@cloudparse/up-backoffice-sdk";
import {
  createRealtimeClient,
  deriveWsUrl,
  type RealtimeEvent,
  type RealtimeStatus,
} from "@plugin/lib/realtimeClient";
import { useEffect, useRef, useState } from "react";

export interface RealtimeLogLine {
  id: number;
  text: string;
}

export interface Realtime {
  /** How many events came in since the page opened. */
  eventCount: number;
  /** When the last event came in, or null. */
  lastEventAt: Date | null;
  /** The newest lines first: state changes and events. */
  log: RealtimeLogLine[];
  status: RealtimeStatus;
}

const LOG_LINES = 6;

interface Options {
  /** Short text for an event in the log. */
  describe?(event: RealtimeEvent): string;
  /** Called for each event of the API. */
  onEvent(event: RealtimeEvent): void;
  /** Called each time the socket opens: read the data again, a push may have been missed. */
  onOpen?(): void;
}

/**
 * Keeps the WebSocket of the mini-app API open while the page is mounted.
 * The address is the one the Studio registered for the mini-app (`application.wsBackendUrl`),
 * or the one derived from the API base URL. The ticket is asked with the admin token.
 */
export function useRealtime(options: Options): Realtime {
  const host = usePluginHost();
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const [eventCount, setEventCount] = useState(0);
  const [log, setLog] = useState<RealtimeLogLine[]>([]);
  // The callbacks change at each render: the client reads the latest through this ref.
  const latest = useRef(options);
  latest.current = options;
  const wsBackendUrl = host.application.wsBackendUrl;
  const apiBaseUrl = host.miniappApi.baseUrl;

  useEffect(() => {
    let line = 0;
    const addLog = (text: string) =>
      setLog((previous) =>
        [
          {
            id: ++line,
            text: `${new Date().toLocaleTimeString("en-GB")} ${text}`,
          },
          ...previous,
        ].slice(0, LOG_LINES),
      );
    const client = createRealtimeClient({
      onEvent: (event) => {
        setLastEventAt(new Date());
        setEventCount((count) => count + 1);
        addLog(latest.current.describe?.(event) ?? event.event);
        latest.current.onEvent(event);
      },
      onLog: addLog,
      onStatus: (next) => {
        setStatus(next);
        if (next === "open") latest.current.onOpen?.();
      },
      ticket: async () =>
        (await miniappApi.post<{ ticket: string }>("/ws-ticket")).ticket,
      url: () => wsBackendUrl || deriveWsUrl(apiBaseUrl),
    });
    client.start();
    return () => client.stop();
  }, [wsBackendUrl, apiBaseUrl]);

  return { eventCount, lastEventAt, log, status };
}
