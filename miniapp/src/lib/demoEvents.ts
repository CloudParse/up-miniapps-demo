/**
 * The events the demo API pushes over its WebSocket (api/app/services/realtime_service.py,
 * docs/realtime.md "Events of the demo") and what each one does to the counters on screen.
 *
 * No import and no browser global: it runs in the browser and in the `node --test` tests
 * (`../../dev-tools/demoEvents.test.ts`).
 */

export const VISIT_RECORDED = "visit_recorded";
export const COUNTER_RESET = "counter_reset";

/** The counters of the "Données de la mini-app" card. `null`: not configured or not known yet. */
export interface DemoCounters {
  cacheVisits: number | null;
  databaseVisits: number | null;
}

export const NO_COUNTERS: DemoCounters = {
  cacheVisits: null,
  databaseVisits: null,
};

function counter(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** True for the events that change a counter. */
export function isDemoEvent(message: { event?: unknown }): boolean {
  return message.event === VISIT_RECORDED || message.event === COUNTER_RESET;
}

/** The counters after one message. Anything else leaves them as they are. */
export function applyDemoEvent(
  counters: DemoCounters,
  message: Record<string, unknown>,
): DemoCounters {
  if (message.event === VISIT_RECORDED) {
    return {
      cacheVisits: counter(message.cacheVisits) ?? counters.cacheVisits,
      databaseVisits:
        counter(message.databaseVisits) ?? counters.databaseVisits,
    };
  }
  if (message.event === COUNTER_RESET) {
    return { ...counters, cacheVisits: counter(message.cacheVisits) ?? 0 };
  }
  return counters;
}

export type DemoLiveStatus = "closed" | "connecting" | "open";

/** The label of the status chip. The SDK reports `connecting` for the first try and for each retry. */
export function liveStatusLabel(
  status: DemoLiveStatus,
  everOpened: boolean,
): string {
  if (status === "open") return "connecté";
  if (status === "connecting") return everOpened ? "reconnexion" : "connexion…";
  return "hors ligne";
}
