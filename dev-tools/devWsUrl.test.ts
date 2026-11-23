import assert from "node:assert/strict";
import { test } from "node:test";
import { devWsUrl, resolveDevBackendUrl } from "../miniapp/src/lib/devWsUrl.ts";

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

test("a path VITE_BACKEND_URL gives a non-empty WebSocket address in the browser (Coder URL)", () => {
  const origin = "https://miniapp--demo--me--app.cloudparse.app";
  const backend = resolveDevBackendUrl("/api/v1", origin);
  assert.equal(backend, `${origin}/api/v1`);
  assert.equal(
    devWsUrl(backend),
    "wss://miniapp--demo--me--app.cloudparse.app/api/v1/ws",
  );
  assert.equal(devWsUrl(resolveDevBackendUrl("", origin)), "");
});
