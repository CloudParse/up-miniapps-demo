// The wire format of the admin routes of the demo API (../api/app/schemas/demo_admin.py).
// `null`: that resource is not configured in the API's environment.
export interface DemoOverview {
  cacheVisits: number | null;
  databaseVisits: number | null;
  storageObjects: number | null;
}
