import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyDemoEvent,
  isDemoEvent,
  liveStatusLabel,
  NO_COUNTERS,
} from "../miniapp/src/lib/demoEvents.ts";

test("a visit replaces both counters", () => {
  const next = applyDemoEvent(NO_COUNTERS, {
    cacheVisits: 3,
    databaseVisits: 8,
    event: "visit_recorded",
  });

  assert.deepEqual(next, { cacheVisits: 3, databaseVisits: 8 });
});

test("a reset puts the cache counter to 0 and keeps the database one", () => {
  const next = applyDemoEvent(
    { cacheVisits: 3, databaseVisits: 8 },
    { cacheVisits: 0, event: "counter_reset" },
  );

  assert.deepEqual(next, { cacheVisits: 0, databaseVisits: 8 });
});

test("an unknown event or a bad value changes nothing", () => {
  const start = { cacheVisits: 3, databaseVisits: 8 };

  assert.equal(applyDemoEvent(start, { event: "demo_message" }), start);
  assert.deepEqual(
    applyDemoEvent(start, { cacheVisits: "x", event: "visit_recorded" }),
    start,
  );
});

test("the card reacts to the two events only", () => {
  assert.equal(isDemoEvent({ event: "visit_recorded" }), true);
  assert.equal(isDemoEvent({ event: "counter_reset" }), true);
  assert.equal(isDemoEvent({ event: "demo_message" }), false);
  assert.equal(isDemoEvent({}), false);
});

test("the status chip says connected, connecting then reconnecting, offline", () => {
  assert.equal(liveStatusLabel("open", true), "connecté");
  assert.equal(liveStatusLabel("connecting", false), "connexion…");
  assert.equal(liveStatusLabel("connecting", true), "reconnexion");
  assert.equal(liveStatusLabel("closed", true), "hors ligne");
});
