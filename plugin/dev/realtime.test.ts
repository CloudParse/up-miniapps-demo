// Run by `npm test` in plugin/ (node's own test runner, no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyDemoEvent,
  describeEvent,
  isDemoEvent,
} from "../src/features/demo/realtimeEvents.ts";
import {
  ATTEMPT_TIMEOUT_MS,
  backoffDelay,
  createRealtimeClient,
  deriveWsUrl,
  KEEPALIVE_MS,
  parseEvent,
  type RealtimeEvent,
  type RealtimeSocket,
  type RealtimeStatus,
  type Timers,
  withTicket,
} from "../src/lib/realtimeClient.ts";
import { devWsUrl } from "./devHost.ts";

class FakeSocket implements RealtimeSocket {
  closed = false;
  sent: string[] = [];
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onopen: (() => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
}

// Timers that only run when the test says so.
function fakeTimers() {
  const timeouts = new Map<number, { ms: number; run: () => void }>();
  const intervals = new Map<number, { ms: number; run: () => void }>();
  let next = 1;
  const timers: Timers = {
    clearInterval: (id) => void intervals.delete(id as number),
    clearTimeout: (id) => void timeouts.delete(id as number),
    setInterval: (run, ms) => {
      intervals.set(next, { ms, run });
      return next++;
    },
    setTimeout: (run, ms) => {
      timeouts.set(next, { ms, run });
      return next++;
    },
  };
  return { intervals, timeouts, timers };
}

function setup(ticket: () => Promise<string | null> = async () => "T1") {
  const sockets: FakeSocket[] = [];
  const statuses: RealtimeStatus[] = [];
  const events: RealtimeEvent[] = [];
  const clock = fakeTimers();
  const client = createRealtimeClient({
    createSocket: (url) => {
      const socket = new FakeSocket(url);
      sockets.push(socket);
      return socket;
    },
    onEvent: (event) => events.push(event),
    onStatus: (status) => statuses.push(status),
    random: () => 1,
    ticket,
    timers: clock.timers,
    url: () => "wss://api.example/api/v1/ws",
  });
  return { client, clock, events, sockets, statuses };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("the address comes from the HTTP base URL when the Studio gives none", () => {
  assert.equal(
    deriveWsUrl("https://api.x.app.cloudparse.app/api/v1"),
    "wss://api.x.app.cloudparse.app/api/v1/ws",
  );
  assert.equal(
    deriveWsUrl("http://localhost:21514/api/v1/"),
    "ws://localhost:21514/api/v1/ws",
  );
  assert.equal(deriveWsUrl("/api/v1"), null);
  assert.equal(
    devWsUrl("http://localhost:21516/api/v1"),
    "ws://localhost:21516/api/v1/ws",
  );
});

test("the ticket goes in the query string, encoded", () => {
  assert.equal(withTicket("wss://h/ws", "a b"), "wss://h/ws?ticket=a%20b");
  assert.equal(withTicket("wss://h/ws?x=1", "t"), "wss://h/ws?x=1&ticket=t");
  assert.equal(withTicket("wss://h/ws", null), "wss://h/ws");
});

test("only a JSON message with an event name is an event", () => {
  assert.deepEqual(parseEvent('{"event":"visit_recorded","cacheVisits":2}'), {
    cacheVisits: 2,
    event: "visit_recorded",
  });
  assert.equal(parseEvent('{"type":"pong","id":1}'), null);
  assert.equal(parseEvent("nope"), null);
  assert.equal(parseEvent(new ArrayBuffer(2)), null);
  assert.equal(parseEvent('{"event":3}'), null);
});

test("the backoff doubles up to 30 s and keeps a jitter", () => {
  assert.equal(
    backoffDelay(0, () => 1),
    1000,
  );
  assert.equal(
    backoffDelay(1, () => 1),
    2000,
  );
  assert.equal(
    backoffDelay(4, () => 1),
    16000,
  );
  assert.equal(
    backoffDelay(10, () => 1),
    30000,
  );
  assert.equal(
    backoffDelay(0, () => 0),
    500,
  );
});

test("it opens the socket with a ticket and reports connecting then open", async () => {
  const { client, sockets, statuses } = setup();
  client.start();
  await tick();

  assert.equal(sockets.length, 1);
  assert.equal(sockets[0]?.url, "wss://api.example/api/v1/ws?ticket=T1");
  sockets[0]?.onopen?.();
  assert.deepEqual(statuses, ["connecting", "open"]);
});

test("a message with an event reaches the page, a pong does not", async () => {
  const { client, events, sockets } = setup();
  client.start();
  await tick();
  sockets[0]?.onopen?.();

  sockets[0]?.onmessage?.({
    data: '{"event":"counter_reset","cacheVisits":0}',
  });
  sockets[0]?.onmessage?.({ data: '{"type":"pong","id":1}' });

  assert.deepEqual(events, [{ cacheVisits: 0, event: "counter_reset" }]);
});

test("a lost socket reconnects with a new ticket and a growing wait", async () => {
  let n = 0;
  const { client, clock, sockets, statuses } = setup(async () => `T${++n}`);
  client.start();
  await tick();
  sockets[0]?.onopen?.();

  sockets[0]?.onclose?.();
  assert.equal(statuses.at(-1), "reconnecting");
  const [first] = [...clock.timeouts.values()];
  assert.equal(first?.ms, 1000);
  first?.run();
  await tick();
  assert.equal(sockets[1]?.url, "wss://api.example/api/v1/ws?ticket=T2");

  // The second attempt fails too: the wait doubles.
  sockets[1]?.onclose?.();
  const waits = [...clock.timeouts.values()].map((t) => t.ms);
  assert.ok(waits.includes(2000));
  // Open again: the wait starts over.
  [...clock.timeouts.values()].at(-1)?.run();
  await tick();
  sockets[2]?.onopen?.();
  assert.equal(statuses.at(-1), "open");
  sockets[2]?.onclose?.();
  assert.equal([...clock.timeouts.values()].at(-1)?.ms, 1000);
});

test("an error closes the socket so the retry happens", async () => {
  const { client, clock, sockets } = setup();
  client.start();
  await tick();

  sockets[0]?.onerror?.();

  assert.equal(sockets[0]?.closed, true);
  assert.equal(clock.timeouts.size, 1);
});

test("without a ticket route it still tries the socket", async () => {
  const { client, sockets } = setup(async () => {
    throw new Error("404");
  });
  client.start();
  await tick();

  assert.equal(sockets[0]?.url, "wss://api.example/api/v1/ws");
});

test("it pings every 60 s while open and stops when the socket is lost", async () => {
  const { client, clock, sockets } = setup();
  client.start();
  await tick();
  sockets[0]?.onopen?.();

  const [ping] = [...clock.intervals.values()];
  assert.equal(ping?.ms, KEEPALIVE_MS);
  ping?.run();
  assert.deepEqual(sockets[0]?.sent, ['{"id":1,"type":"ping"}']);

  sockets[0]?.onclose?.();
  assert.equal(clock.intervals.size, 0);
});

test("stop closes the socket, cancels the retry and goes offline", async () => {
  const { client, clock, sockets, statuses } = setup();
  client.start();
  await tick();
  sockets[0]?.onopen?.();
  sockets[0]?.onclose?.();
  assert.equal(clock.timeouts.size, 1);

  client.stop();

  assert.equal(clock.timeouts.size, 0);
  assert.equal(statuses.at(-1), "offline");
  assert.equal(sockets.length, 1);
});

test("stop while the ticket is requested opens no socket", async () => {
  const { client, sockets } = setup(async () => {
    await tick();
    return "T";
  });
  client.start();
  client.stop();
  await tick();
  await tick();

  assert.equal(sockets.length, 0);
});

test("no address: the client stays offline and does not retry", async () => {
  const statuses: RealtimeStatus[] = [];
  const clock = fakeTimers();
  const client = createRealtimeClient({
    createSocket: () => {
      throw new Error("must not open");
    },
    onEvent: () => {},
    onStatus: (status) => statuses.push(status),
    ticket: async () => null,
    timers: clock.timers,
    url: () => null,
  });
  client.start();
  await tick();

  assert.deepEqual(statuses, ["connecting", "offline"]);
  assert.equal(clock.timeouts.size, 0);
});

test("a visit updates both counters, a reset puts the cache counter to 0", () => {
  const overview = { cacheVisits: 4, databaseVisits: 9, storageObjects: 2 };

  assert.deepEqual(
    applyDemoEvent(overview, {
      cacheVisits: 5,
      databaseVisits: 10,
      event: "visit_recorded",
    }),
    { cacheVisits: 5, databaseVisits: 10, storageObjects: 2 },
  );
  assert.deepEqual(
    applyDemoEvent(overview, { cacheVisits: 0, event: "counter_reset" }),
    { cacheVisits: 0, databaseVisits: 9, storageObjects: 2 },
  );
  assert.equal(applyDemoEvent(overview, { event: "other" }), overview);
  assert.deepEqual(
    applyDemoEvent(overview, { cacheVisits: "x", event: "visit_recorded" }),
    overview,
  );
});

test("the page knows its two events and describes them", () => {
  assert.equal(isDemoEvent({ event: "visit_recorded" }), true);
  assert.equal(isDemoEvent({ event: "counter_reset" }), true);
  assert.equal(isDemoEvent({ event: "demo_message" }), false);
  assert.match(
    describeEvent({
      cacheVisits: 5,
      databaseVisits: 10,
      event: "visit_recorded",
    }),
    /database 10, cache 5/,
  );
  assert.equal(describeEvent({ event: "demo_message" }), "demo_message");
});

test("a handshake stuck in connecting is dropped and retried", async () => {
  const { client, clock, sockets, statuses } = setup();
  client.start();
  await tick();
  assert.equal(sockets.length, 1);

  const attempt = [...clock.timeouts.values()].find(
    (t) => t.ms === ATTEMPT_TIMEOUT_MS,
  );
  attempt?.run();

  assert.equal(sockets[0]?.closed, true);
  assert.equal(statuses.at(-1), "reconnecting");
  assert.ok([...clock.timeouts.values()].some((t) => t.ms === 1000));
});
