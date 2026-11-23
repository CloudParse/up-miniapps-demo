import assert from "node:assert/strict";
import { test } from "node:test";
import { devWsUrl } from "../miniapp/src/lib/devWsUrl.ts";

test("the development WebSocket address follows the development backend URL", () => {
  assert.equal(
    devWsUrl("http://localhost:21515/api/v1"),
    "ws://localhost:21515/api/v1/ws",
  );
  assert.equal(
    devWsUrl("https://miniapp--demo--me--app.cloudparse.app/api/v1/"),
    "wss://miniapp--demo--me--app.cloudparse.app/api/v1/ws",
  );
});

test("no development backend URL gives no address", () => {
  assert.equal(devWsUrl(""), "");
  assert.equal(devWsUrl("/api/v1"), "");
});
