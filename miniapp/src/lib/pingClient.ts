/**
 * Ping/pong over the WebSocket of the API, so a student SEES that realtime works.
 *
 * The SDK broadcast client (`createWsService`) only listens: it has no `send`. This small
 * client owns a second socket to the same address and talks both ways: it sends
 * `{"type":"ping","id":n}` and the API answers `{"type":"pong","id":n,"serverTime":...}` to
 * this socket only (it is not a broadcast). It measures the round trip with its own clock.
 *
 * No import and no browser global at module level: it runs in the browser and in the
 * `node --test` tests (`../dev-tools/pingClient.test.ts`).
 */

export type PingStatus = "closed" | "connecting" | "open";

export interface PingResult {
  id: number;
  /** Round trip in ms, measured by this client. */
  roundTripMs: number;
  /** Clock of the server when it answered (ISO 8601). */
  serverTime: string;
}

/** The part of the browser `WebSocket` this client needs (a fake in the tests). */
export interface PingSocket {
  send(data: string): void;
  close(): void;
  onopen: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
}

export interface PingClientOptions {
  /** The WebSocket address given by the platform, never hard-coded. */
  url: string;
  onStatus(status: PingStatus): void;
  onPong(result: PingResult): void;
  /** One line per frame sent or received, for the on-screen log. */
  onLog?(line: string): void;
  createSocket?(url: string): PingSocket;
  now?(): number;
}

export interface PingClient {
  connect(): void;
  disconnect(): void;
  /** Sends a ping. False when the socket is not open. */
  ping(): boolean;
}

const MAX_PENDING = 20;

export function createPingClient(options: PingClientOptions): PingClient {
  const now = options.now ?? (() => Date.now());
  const create =
    options.createSocket ??
    ((url: string) => new WebSocket(url) as unknown as PingSocket);
  let socket: PingSocket | null = null;
  let status: PingStatus = "closed";
  let nextId = 1;
  // id -> time the ping left. Bounded: a server that never answers cannot grow it.
  const pending = new Map<number, number>();

  const setStatus = (next: PingStatus) => {
    if (status === next) return;
    status = next;
    options.onStatus(next);
  };

  return {
    connect() {
      if (socket) return;
      setStatus("connecting");
      const opened = create(options.url);
      socket = opened;
      opened.onopen = () => {
        if (socket !== opened) return;
        setStatus("open");
        options.onLog?.("connecté");
      };
      opened.onmessage = (event) => {
        if (socket !== opened || typeof event.data !== "string") return;
        let data: unknown;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        if (typeof data !== "object" || data === null) return;
        const message = data as Record<string, unknown>;
        if (
          message.type === "pong" &&
          typeof message.id === "number" &&
          typeof message.serverTime === "string"
        ) {
          const sentAt = pending.get(message.id);
          if (sentAt === undefined) return;
          pending.delete(message.id);
          const roundTripMs = Math.max(0, now() - sentAt);
          options.onLog?.(`pong #${message.id} en ${roundTripMs} ms`);
          options.onPong({
            id: message.id,
            roundTripMs,
            serverTime: message.serverTime,
          });
        }
      };
      const closed = () => {
        if (socket !== opened) return;
        socket = null;
        pending.clear();
        setStatus("closed");
        options.onLog?.("déconnecté");
      };
      opened.onclose = closed;
      opened.onerror = closed;
    },
    disconnect() {
      const current = socket;
      if (!current) return;
      socket = null;
      pending.clear();
      current.onopen = null;
      current.onmessage = null;
      current.onclose = null;
      current.onerror = null;
      current.close();
      setStatus("closed");
      options.onLog?.("déconnecté");
    },
    ping() {
      if (!socket || status !== "open") return false;
      if (pending.size >= MAX_PENDING) pending.clear();
      const id = nextId++;
      pending.set(id, now());
      socket.send(JSON.stringify({ id, type: "ping" }));
      options.onLog?.(`ping #${id}`);
      return true;
    },
  };
}
