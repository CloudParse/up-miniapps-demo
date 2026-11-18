// A path such as "/api/v1" goes through the Vite dev server's proxy to the
// backend (vite.config.ts): one origin, so it works the same on localhost and
// behind a Coder port URL. The SDK needs an absolute URL.
function resolveDevBackendUrl(raw: string | undefined): string {
  const value = raw?.trim() ?? "";
  return value.startsWith("/") ? `${window.location.origin}${value}` : value;
}

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
