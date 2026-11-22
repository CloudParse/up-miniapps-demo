// Development only: the URLs and the API check of the development page (`dev/main.tsx`).
// Kept apart from main.tsx so node's test runner can run them (`npm test`).

const FALLBACK_ORIGIN = "http://localhost:21516";

/**
 * The origin the page is served from, or localhost when the browser gives none usable
 * ("null" for a file:// page, an empty string). Coder gives
 * `https://21516--main--<workspace>--<owner>--<organisation>.<domain>`.
 */
export function pageOrigin(origin: string | undefined | null): string {
  try {
    const parsed = new URL(origin ?? "");
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.origin
      : FALLBACK_ORIGIN;
  } catch {
    return FALLBACK_ORIGIN;
  }
}

/**
 * The SDK's `ApiService` builds every request with `new URL(baseUrl + path)`. A relative
 * base such as "/api/v1" makes that throw "Failed to construct 'URL': Invalid URL", so
 * the base must be absolute. The Vite server proxies `/api/` and `/hub/` (vite.dev.config.ts).
 */
export function devBaseUrls(origin: string | undefined | null): {
  api: string;
  hub: string;
  hubLogin: string;
} {
  const base = pageOrigin(origin);
  return {
    api: `${base}/api/v1`,
    hub: `${base}/hub/api/v1`,
    hubLogin: `/hub/api/v1`,
  };
}

/**
 * Asks the API for `/api/v1/hello` through the Vite proxy. Returns a message for the
 * developer when the API does not answer, or null when it does. The Vite proxy answers
 * 500, 502 or 504 when the API is down, a network error when Vite itself is.
 */
export async function apiProblem(
  apiBase: string,
  fetchFn: typeof fetch = fetch,
): Promise<string | null> {
  const start =
    "Start it in another terminal: cd api && uv run python -m app (port 21514).";
  try {
    const response = await fetchFn(`${apiBase}/hello`);
    if (response.status >= 500) {
      return `The mini-app API does not answer (HTTP ${response.status} from the dev proxy). ${start}`;
    }
    return null;
  } catch {
    return `The development server does not answer. Check that "npm run dev" still runs. ${start}`;
  }
}
