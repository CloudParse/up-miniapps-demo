import { apiService } from "@app/services/backend";

// Route of the demo backend (backend/app/api/routes/demo.py), served under /api/v1.
export const DEMO_VISIT_PATH = "demo/visit";

/** Wire shape returned by `POST /api/v1/demo/visit` (backend/app/schemas/demo.py). */
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
