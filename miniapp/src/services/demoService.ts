import { apiService } from "@app/services/backend";

// Routes of the demo API (api/app/api/routes/demo.py), served under /api/v1 outside production only.
export const DEMO_PATH = "demo";
export const DEMO_VISIT_PATH = "demo/visit";
export const DEMO_BROADCAST_PATH = "demo/broadcast";

/** Wire shape returned by `POST /api/v1/demo/visit` (api/app/schemas/demo.py). */
interface IBackendDemoVisit {
  databaseVisits: number | null;
  cacheVisits: number | null;
  storageObject: string | null;
}

export interface DemoVisit {
  databaseVisits: number | null;
  cacheVisits: number | null;
  storageObject: string | null;
}

// The one place the wire shape becomes the UI shape.
function mapBackendDemoVisit(visit: IBackendDemoVisit): DemoVisit {
  return {
    cacheVisits: visit.cacheVisits,
    databaseVisits: visit.databaseVisits,
    storageObject: visit.storageObject,
  };
}

/** Writes one row, one counter and one object in the mini-app's own resources and reads them back. */
export async function recordDemoVisit(): Promise<DemoVisit> {
  return mapBackendDemoVisit(
    await apiService.post<IBackendDemoVisit>(DEMO_VISIT_PATH, {}),
  );
}

/** True when the API serves the demo. In production the route does not exist (404): the card stays hidden. */
export async function isDemoServed(): Promise<boolean> {
  try {
    await apiService.get<{ enabled: boolean }>(DEMO_PATH);
    return true;
  } catch {
    return false;
  }
}

/**
 * Asks the API to push a message to every open WebSocket (`POST /api/v1/demo/broadcast`).
 * The message comes back through the socket of the "Temps réel" screen, not through this call:
 * the SDK's WebSocket client only listens. Returns how many sockets received it.
 */
export async function broadcastDemoMessage(text: string): Promise<number> {
  const result = await apiService.post<{ delivered: number }>(
    DEMO_BROADCAST_PATH,
    { text },
  );
  return result.delivered;
}
