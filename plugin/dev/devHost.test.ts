// Run by `npm test` in plugin/ (node's own test runner, no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import { apiProblem, devBaseUrls, pageOrigin } from "./devHost.ts";

const CODER =
  "https://21516--main--test2--thoughtful-lawson93--app.cloudparse.app";

test("a relative base URL is what made the SDK throw", () => {
  assert.throws(() => new URL("/api/v1/admin/demo/overview"), TypeError);
});

test("the bases are absolute for Coder, localhost and a missing origin", () => {
  for (const origin of [
    CODER,
    "http://localhost:21516",
    "",
    undefined,
    "null",
  ]) {
    const { api, hub } = devBaseUrls(origin);
    assert.doesNotThrow(() => new URL(`${api}/admin/demo/overview`));
    assert.doesNotThrow(() => new URL(`${hub}/auth/login`));
  }
  assert.equal(devBaseUrls(CODER).api, `${CODER}/api/v1`);
  assert.equal(devBaseUrls(undefined).api, "http://localhost:21516/api/v1");
});

test("pageOrigin drops the path and refuses other schemes", () => {
  assert.equal(pageOrigin(`${CODER}/some/path`), CODER);
  assert.equal(pageOrigin("file:///tmp/x.html"), "http://localhost:21516");
});

test("apiProblem is null when the API answers, even with 401 or 404", async () => {
  for (const status of [200, 401, 404]) {
    const fetchFn = (async () => new Response("", { status })) as typeof fetch;
    assert.equal(await apiProblem("http://x/api/v1", fetchFn), null);
  }
});

test("apiProblem explains a proxy 500 and a network error", async () => {
  const down = (async () => new Response("", { status: 500 })) as typeof fetch;
  assert.match(
    (await apiProblem("http://x/api/v1", down)) ?? "",
    /uv run python -m app/,
  );
  const dead = (async () => {
    throw new TypeError("Failed to fetch");
  }) as typeof fetch;
  assert.match(
    (await apiProblem("http://x/api/v1", dead)) ?? "",
    /npm run dev/,
  );
});
