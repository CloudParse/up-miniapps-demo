import { miniappApi } from "@cloudparse/up-backoffice-sdk";
import type { DemoNote, DemoOverview } from "@plugin/features/demo/types";

// The plugin never holds a database, cache or bucket credential. It calls the admin routes
// of the mini-app API through `miniappApi`: the Studio runs the request with an admin
// token, and the API reads PostgreSQL, the cache and the bucket with its own settings.
// Paths start after the API base URL, which already ends with /api/v1.
export const demoService = {
  // An admin puts data into the database: the plugin sends the text, the API writes the row.
  addNote: (text: string) =>
    miniappApi.post<DemoNote>("/admin/demo/notes", { text }),
  listNotes: () => miniappApi.get<DemoNote[]>("/admin/demo/notes"),
  overview: () => miniappApi.get<DemoOverview>("/admin/demo/overview"),
  resetCache: () => miniappApi.post<DemoOverview>("/admin/demo/reset-cache"),
};
