import {
  applyDemoEvent,
  type DemoCounters,
  type DemoLiveStatus,
  isDemoEvent,
  NO_COUNTERS,
} from "@app/lib/demoEvents";
import { apiClient, getWsUrl } from "@app/services/backend";
import { readDemoCounters } from "@app/services/demoService";
import { createWsService } from "@cloudparse/up-miniapps-sdk";
import { useCallback, useEffect, useRef, useState } from "react";

export interface DemoLive {
  counters: DemoCounters;
  /** True once the socket has been open at least once: a later `connecting` is a reconnection. */
  everOpened: boolean;
  lastEventAt: Date | null;
  /** True once the API answered a read: a null counter is then "not configured", not "unknown". */
  loaded: boolean;
  /** Sets the counters from an HTTP answer (the response of "Enregistrer une visite"). */
  set(counters: DemoCounters): void;
  status: DemoLiveStatus;
}

/**
 * Keeps the counters of the demo card live: reads them once, then each push of the API
 * (`visit_recorded`, `counter_reset`) replaces them, from this mini-app or from the plugin.
 * After each (re)connection the counters are read again: a push sent while offline is not lost.
 * `enabled` false (the demo is not served): nothing is opened.
 */
export function useDemoLive(enabled: boolean): DemoLive {
  const [counters, setCounters] = useState<DemoCounters>(NO_COUNTERS);
  const [status, setStatus] = useState<DemoLiveStatus>("closed");
  const [everOpened, setEverOpened] = useState(false);
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const [loaded, setLoaded] = useState(false);
  // Bumped by every push and every local answer: an older HTTP read must not overwrite a newer figure.
  const version = useRef(0);
  const wsUrl = getWsUrl();

  useEffect(() => {
    if (!enabled || !wsUrl) return;
    let alive = true;
    const reload = () => {
      const started = version.current;
      readDemoCounters()
        .then((next) => {
          if (!alive) return;
          setLoaded(true);
          if (version.current === started) setCounters(next);
        })
        .catch(() => undefined);
    };
    // requireAuth false: the SDK asks a ticket inside the Up shell, and opens the public socket
    // of the demo in a plain browser (development), where it has no token.
    const ws = createWsService({ api: apiClient, requireAuth: false });
    const offStatus = ws.onStatusChange((next) => {
      setStatus(next);
      if (next === "open") {
        setEverOpened(true);
        reload();
      }
    });
    const offMessages = ws.onMessage((message) => {
      if (!isDemoEvent(message)) return;
      version.current += 1;
      setLastEventAt(new Date());
      setCounters((current) => applyDemoEvent(current, message));
    });
    return () => {
      alive = false;
      offStatus();
      offMessages();
      ws.disconnect();
    };
  }, [enabled, wsUrl]);

  const set = useCallback((next: DemoCounters) => {
    version.current += 1;
    setLoaded(true);
    setCounters(next);
  }, []);
  return { counters, everOpened, lastEventAt, loaded, set, status };
}
