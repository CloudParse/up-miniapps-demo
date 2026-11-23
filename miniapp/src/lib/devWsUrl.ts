/**
 * WebSocket address of the demo API in development, from the (absolute) development backend URL: same host, ws or wss scheme, `/ws`
 * route of the API. Used only as the last fallback: the address the platform registers always wins (window.__UP_BACKEND_URLS__, then
 * the shell env). Empty in production, where the platform provides it, and when no development backend URL is set.
 */
export function devWsUrl(backendUrl: string): string {
  const url = backendUrl.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//.test(url)) return "";
  return `${url.replace(/^http/, "ws")}/ws`;
}

// A path such as "/api/v1" goes through the Vite dev server's proxy to the
// backend (vite.config.ts): one origin, so it works the same on localhost and
// behind a Coder port URL. The SDK needs an absolute URL.
export function resolveDevBackendUrl(
  raw: string | undefined,
  origin: string = window.location.origin,
): string {
  const value = raw?.trim() ?? "";
  return value.startsWith("/") ? `${origin}${value}` : value;
}
