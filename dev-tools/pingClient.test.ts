import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createPingClient,
  type PingResult,
  type PingSocket,
  type PingStatus,
} from "../miniapp/src/lib/pingClient.ts";

class FakeSocket implements PingSocket {
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
}

function setup() {
  const sockets: FakeSocket[] = [];
  const statuses: PingStatus[] = [];
  const pongs: PingResult[] = [];
  const log: string[] = [];
  let clock = 1000;
  const client = createPingClient({
    createSocket: () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
    now: () => clock,
    onLog: (line) => log.push(line),
    onPong: (result) => pongs.push(result),
    onStatus: (status) => statuses.push(status),
    url: "wss://api.example/api/v1/ws",
  });
  return {
    advance: (ms: number) => {
      clock += ms;
    },
    client,
    log,
    pongs,
    sockets,
    statuses,
  };
}

test("a ping is refused until the socket is open", () => {
  const { client, sockets } = setup();
  assert.equal(client.ping(), false);
  client.connect();
  assert.equal(client.ping(), false);
  sockets[0]?.onopen?.();
  assert.equal(client.ping(), true);
});

test("a ping leaves as JSON and its pong gives the round trip", () => {
  const { client, sockets, advance, pongs, log } = setup();
  client.connect();
  const socket = sockets[0] as FakeSocket;
  socket.onopen?.();
  client.ping();
  assert.deepEqual(JSON.parse(socket.sent[0] as string), {
    id: 1,
    type: "ping",
  });
  advance(42);
  socket.onmessage?.({
    data: JSON.stringify({
      id: 1,
      serverTime: "2026-11-23T10:00:00+00:00",
      type: "pong",
    }),
  });
  assert.deepEqual(pongs, [
    { id: 1, roundTripMs: 42, serverTime: "2026-11-23T10:00:00+00:00" },
  ]);
  assert.ok(log.includes("pong #1 en 42 ms"));
});

test("a pong nobody asked for, a broadcast and garbage are ignored", () => {
  const { client, sockets, pongs } = setup();
  client.connect();
  const socket = sockets[0] as FakeSocket;
  socket.onopen?.();
  client.ping();
  for (const data of [
    JSON.stringify({ id: 99, serverTime: "x", type: "pong" }),
    JSON.stringify({ event: "demo_message", text: "salut" }),
    JSON.stringify({ id: null, serverTime: "x", type: "pong" }),
    "not json",
    42,
  ]) {
    socket.onmessage?.({ data });
  }
  assert.deepEqual(pongs, []);
});

test("status follows the socket and a close forgets the pending pings", () => {
  const { client, sockets, statuses, pongs } = setup();
  client.connect();
  const socket = sockets[0] as FakeSocket;
  socket.onopen?.();
  client.ping();
  socket.onclose?.();
  assert.deepEqual(statuses, ["connecting", "open", "closed"]);
  // a late pong of the old socket is not delivered
  socket.onmessage?.({
    data: JSON.stringify({ id: 1, serverTime: "x", type: "pong" }),
  });
  assert.deepEqual(pongs, []);
  assert.equal(client.ping(), false);
});

test("disconnect closes the socket and connect opens a new one", () => {
  const { client, sockets, statuses } = setup();
  client.connect();
  client.connect();
  assert.equal(sockets.length, 1, "connect twice opens one socket");
  (sockets[0] as FakeSocket).onopen?.();
  client.disconnect();
  assert.equal((sockets[0] as FakeSocket).closed, true);
  client.connect();
  assert.equal(sockets.length, 2);
  assert.deepEqual(statuses, ["connecting", "open", "closed", "connecting"]);
});
