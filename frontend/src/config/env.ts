export const APP_CONFIG = {
  appName: "Up Demo",
  backendUrl: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_BACKEND_URL?.trim() ?? ""),
  devToken: import.meta.env.PROD
    ? ""
    : (import.meta.env.VITE_DEV_TOKEN?.trim() ?? ""),
  isDev: import.meta.env.DEV,
} as const;
