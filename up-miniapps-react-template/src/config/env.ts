// Single place that reads import.meta.env. Dev-only values are blanked in a
// production build so a local URL or token can never ship in the bundle.
export const APP_CONFIG = {
  appName: "Up Mini-App",
  backendUrl: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_BACKEND_URL?.trim() ?? ""),
  devToken: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_DEV_TOKEN?.trim() ?? ""),
} as const;
