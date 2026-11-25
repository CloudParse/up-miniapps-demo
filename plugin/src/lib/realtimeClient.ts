/**
 * The realtime client of the plugin: one WebSocket to the mini-app API, with a visible state.
 *
 * The SDK of the Studio has no WebSocket helper, so the plugin owns this small client. It:
 *   - opens `<wsUrl>?ticket=<ticket>` (the ticket comes from `POST /ws-ticket`, asked with the admin token),
 *   - reconnects by itself with an exponential backoff (1 s, 2 s, 4 s ... 30 s, with jitter),
 *   - sends a ping every 60 s so the API does not close an idle socket (it does after 5 minutes),
 *   - reports its state (`connecting`, `open`, `reconnecting`, `offline`) so the page can show it.
 *
 * No import and no browser global at module level: it runs in the Studio frame and in the
 * `node --test` tests (`../../dev/realtime.test.ts`).
 */

export type RealtimeStatus = "connecting" | "open" | "reconnecting" | "offline";

/** One message of the API: `{ "event": "<name>", ...fields }` (docs/realtime.md, "Events of the demo"). */
export interface RealtimeEvent {
  event: string;
  [key: string]: unknown;
}

/** The part of the browser `WebSocket` this client needs (a fake in the tests). */
export interface RealtimeSocket {
  close(): void;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onopen: (() => void) | null;
  send(data: string): void;
}

export interface Timers {
  clearInterval(id: unknown): void;
  clearTimeout(id: unknown): void;
  setInterval(callback: () => void, ms: number): unknown;
  setTimeout(callback: () => void, ms: number): unknown;
}

export interface RealtimeClientOptions {
  createSocket?(url: string): RealtimeSocket;
  /** One line per state change, for the on-screen log. */
  onLog?(line: string): void;
  onEvent(event: RealtimeEvent): void;
  onStatus(status: RealtimeStatus): void;
  random?(): number;
  /** A single-use ticket, or null when the API has no ticket route. May throw. */
  ticket(): Promise<string | null>;
  timers?: Timers;
  /** The WebSocket address, read at each attempt. Null: not configured, the client stays offline. */
  url(): string | null;
}

export interface RealtimeClient {
  start(): void;
  stop(): void;
}

export const BACKOFF_START_MS = 1000;
export const BACKOFF_MAX_MS = 30_000;
export const KEEPALIVE_MS = 60_000;
/** An attempt (ticket + handshake) that is not open after this long is dropped and retried. */
export const ATTEMPT_TIMEOUT_MS = 10_000;

/** The wait before attempt number `attempt` (0 for the first retry), jitter included. */
export function backoffDelay(attempt: number, random: () => number): number {
  const base = Math.min(BACKOFF_MAX_MS, BACKOFF_START_MS * 2 ** attempt);
  // Between 50% and 100% of the base: many plugins do not retry at the same moment.
  return Math.round(base * (0.5 + random() * 0.5));
}

/**
 * The WebSocket address from the HTTP base URL of the API (`https://host/api/v1` becomes
 * `wss://host/api/v1/ws`). Used only when the Studio gives no `wsBackendUrl`.
 */
export function deriveWsUrl(httpBaseUrl: string): string | null {
  const base = httpBaseUrl.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//.test(base)) return null;
  return `${base.replace(/^http/, "ws")}/ws`;
}

/** The message as an event, or null for anything else (a pong, text that is not JSON). */
export function parseEvent(data: unknown): RealtimeEvent | null {
  if (typeof data !== "string") return null;
  try {
    const parsed: unknown = JSON.parse(data);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      typeof (parsed as { event?: unknown }).event === "string"
    ) {
      return parsed as RealtimeEvent;
    }
  } catch {
    // Not JSON: ignored.
  }
  return null;
}

export function withTicket(url: string, ticket: string | null): string {
  if (ticket === null) return url;
  return `${url}${url.includes("?") ? "&" : "?"}ticket=${encodeURIComponent(ticket)}`;
}

const BROWSER_TIMERS: Timers = {
  clearInterval: (id) => clearInterval(id as number),
  clearTimeout: (id) => clearTimeout(id as number),
  setInterval: (callback, ms) => setInterval(callback, ms),
  setTimeout: (callback, ms) => setTimeout(callback, ms),
};

export function createRealtimeClient(
  options: RealtimeClientOptions,
): RealtimeClient {
  const timers = options.timers ?? BROWSER_TIMERS;
  const random = options.random ?? Math.random;
  const create =
    options.createSocket ??
    ((url: string) => new WebSocket(url) as unknown as RealtimeSocket);
  let running = false;
  let socket: RealtimeSocket | null = null;
  let retryTimer: unknown = null;
  let keepalive: unknown = null;
  let attemptTimer: unknown = null;
  let attempt = 0;
  let pingId = 0;
  let status: RealtimeStatus = "offline";
  // Bumped by every start and stop: an attempt that finishes late sees it changed and gives up.
  let generation = 0;

  const setStatus = (next: RealtimeStatus) => {
    if (status === next) return;
    status = next;
    options.onStatus(next);
  };

  const stopKeepalive = () => {
    if (keepalive !== null) timers.clearInterval(keepalive);
    keepalive = null;
  };

  const clearAttemptTimer = () => {
    if (attemptTimer !== null) timers.clearTimeout(attemptTimer);
    attemptTimer = null;
  };

  const scheduleRetry = () => {
    if (!running) return;
    const delay = backoffDelay(attempt, random);
    attempt += 1;
    setStatus("reconnecting");
    options.onLog?.(`reconnecting in ${Math.round(delay / 100) / 10} s`);
    retryTimer = timers.setTimeout(() => {
      retryTimer = null;
      void connect();
    }, delay);
  };

  const connect = async (): Promise<void> => {
    const mine = generation;
    setStatus(attempt === 0 ? "connecting" : "reconnecting");
    clearAttemptTimer();
    // A hung ticket request or a handshake stuck in CONNECTING must not freeze the chip.
    attemptTimer = timers.setTimeout(() => {
      attemptTimer = null;
      if (mine !== generation || status === "open") return;
      generation += 1;
      const stuck = socket;
      socket = null;
      if (stuck) {
        stuck.onclose = null;
        stuck.onerror = null;
        stuck.onmessage = null;
        stuck.close();
      }
      options.onLog?.("attempt timed out");
      scheduleRetry();
    }, ATTEMPT_TIMEOUT_MS);
    const url = options.url();
    if (!url) {
      clearAttemptTimer();
      setStatus("offline");
      options.onLog?.("no WebSocket address for this mini-app");
      return;
    }
    let ticket: string | null = null;
    try {
      ticket = await options.ticket();
    } catch {
      // The API stays reachable without a ticket unless it requires one: try, the socket decides.
      options.onLog?.("no ticket, trying without");
    }
    if (mine !== generation) return;
    let opened: RealtimeSocket;
    try {
      opened = create(withTicket(url, ticket));
    } catch {
      scheduleRetry();
      return;
    }
    socket = opened;
    opened.onopen = () => {
      if (socket !== opened) return;
      attempt = 0;
      clearAttemptTimer();
      setStatus("open");
      options.onLog?.("connected");
      stopKeepalive();
      keepalive = timers.setInterval(() => {
        pingId += 1;
        try {
          opened.send(JSON.stringify({ id: pingId, type: "ping" }));
        } catch {
          // The socket is closing: its close event starts the retry.
        }
      }, KEEPALIVE_MS);
    };
    opened.onmessage = (message) => {
      if (socket !== opened) return;
      const event = parseEvent(message.data);
      if (event) options.onEvent(event);
    };
    const lost = () => {
      if (socket !== opened) return;
      socket = null;
      stopKeepalive();
      clearAttemptTimer();
      scheduleRetry();
    };
    opened.onclose = lost;
    opened.onerror = () => {
      // A failed handshake also ends in `close`; closing here makes sure it does.
      opened.close();
    };
  };

  return {
    start() {
      if (running) return;
      running = true;
      generation += 1;
      attempt = 0;
      void connect();
    },
    stop() {
      running = false;
      generation += 1;
      if (retryTimer !== null) timers.clearTimeout(retryTimer);
      retryTimer = null;
      clearAttemptTimer();
      stopKeepalive();
      const closing = socket;
      socket = null;
      if (closing) {
        closing.onclose = null;
        closing.onerror = null;
        closing.onmessage = null;
        closing.close();
      }
      setStatus("offline");
    },
  };
}
