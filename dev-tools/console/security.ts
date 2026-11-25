// Request checks of the console: Host and Origin against the same allowlist as the Vite servers (../hostGuard.ts), the CSRF token,
// and the rate limits of the actions. Pure functions: server.ts calls them, the tests call them.
import { timingSafeEqual } from "node:crypto";
import { isAllowedHost } from "../hostGuard.ts";

/** Whether the Host header names an allowed host (loopback names, the Coder button/port host, DEV_ALLOWED_HOSTS). IP addresses are refused. */
export function hostAllowed(header: string | undefined, allowed: readonly string[]): boolean {
  // a Host header is a name (or [ipv6]) and an optional numeric port, nothing else: it is later written into the page's CSP
  if (typeof header !== "string" || !/^(?:[a-z0-9.-]+|\[[0-9a-f:]+\])(?::\d{1,5})?$/i.test(header.trim())) return false;
  return isAllowedHost(header, allowed);
}

/**
 * Whether the Origin header is the console itself: an allowed host AND the same host:port as the Host header.
 * An absent Origin is refused (a browser always sends one on a POST and on a WebSocket upgrade).
 */
export function originAllowed(
  origin: string | undefined,
  host: string | undefined,
  allowed: readonly string[],
): boolean {
  if (!origin || !host) return false;
  let parsed: URL;
  try {
    parsed = new URL(origin);
  } catch {
    return false;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;
  if (parsed.host.toLowerCase() !== host.trim().toLowerCase()) return false;
  return isAllowedHost(parsed.host, allowed);
}

/** Constant-time comparison of the CSRF token. */
export function tokenMatches(given: string | undefined | null, expected: string): boolean {
  if (typeof given !== "string") return false;
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

/** Sliding-window limiter: at most `max` hits per key in `windowMs`. `now` is injectable for the tests. */
export function createRateLimiter(max: number, windowMs: number, now: () => number = Date.now) {
  const hits = new Map<string, number[]>();
  return {
    /** Records a hit and tells whether it is allowed. A refused hit is not recorded. */
    allow(key: string): boolean {
      const t = now();
      const recent = (hits.get(key) ?? []).filter((time) => t - time < windowMs);
      if (recent.length >= max) {
        hits.set(key, recent);
        return false;
      }
      recent.push(t);
      hits.set(key, recent);
      return true;
    },
  };
}
