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
