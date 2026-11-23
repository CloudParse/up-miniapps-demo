import { resolveDevBackendUrl } from "@app/lib/devWsUrl";

export const APP_CONFIG = {
  appName: "Up Demo",
  backendUrl: import.meta.env.PROD
    ? ""
    : resolveDevBackendUrl(import.meta.env.VITE_BACKEND_URL),
  devToken: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_DEV_TOKEN?.trim() ?? ""),
  isDev: import.meta.env.DEV,
} as const;
