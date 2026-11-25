// The events the demo API pushes over its WebSocket (api/app/services/realtime_service.py,
// docs/realtime.md "Events of the demo") and what each one does to the figures on the page.
import type { DemoOverview } from "@plugin/features/demo/types";
import type { RealtimeEvent } from "@plugin/lib/realtimeClient";

export const VISIT_RECORDED = "visit_recorded";
export const COUNTER_RESET = "counter_reset";

function counter(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** True for the events that change a figure of the page. */
export function isDemoEvent(event: RealtimeEvent): boolean {
  return event.event === VISIT_RECORDED || event.event === COUNTER_RESET;
}

/**
 * The overview after `event`. Unknown events leave it as it is. The bucket count is not in
 * the events: the page reads the overview again from the API right after to get it.
 */
export function applyDemoEvent(
  overview: DemoOverview,
  event: RealtimeEvent,
): DemoOverview {
  if (event.event === VISIT_RECORDED) {
    return {
      ...overview,
      cacheVisits: counter(event.cacheVisits) ?? overview.cacheVisits,
      databaseVisits: counter(event.databaseVisits) ?? overview.databaseVisits,
    };
  }
  if (event.event === COUNTER_RESET) {
    return { ...overview, cacheVisits: counter(event.cacheVisits) ?? 0 };
  }
  return overview;
}

/** One short line for the event log of the page. */
export function describeEvent(event: RealtimeEvent): string {
  if (event.event === VISIT_RECORDED) {
    return `visit recorded (database ${counter(event.databaseVisits) ?? "-"}, cache ${counter(event.cacheVisits) ?? "-"})`;
  }
  if (event.event === COUNTER_RESET) return "cache counter reset";
  return event.event;
}
