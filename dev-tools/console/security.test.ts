import assert from "node:assert/strict";
import { test } from "node:test";
import { createRateLimiter, hostAllowed, originAllowed, tokenMatches } from "./security.ts";

const ALLOWED = ["console--ws--owner--org.cloudparse.app"];

test("hostAllowed: loopback names and the button host, never an IP or another host", () => {
  assert.ok(hostAllowed("localhost:21513", ALLOWED));
  assert.ok(hostAllowed("127.0.0.1:21513", ALLOWED));
  assert.ok(hostAllowed("console--ws--owner--org.cloudparse.app", ALLOWED));
  assert.ok(!hostAllowed("10.0.0.5:21513", ALLOWED));
  assert.ok(!hostAllowed("evil.example.com", ALLOWED));
  assert.ok(!hostAllowed("console--ws--other--org.cloudparse.app", ALLOWED));
  assert.ok(!hostAllowed(undefined, ALLOWED));
  // header injection into the CSP, a non-numeric port, spaces
  assert.ok(!hostAllowed("localhost:1 ; script-src * ; object-src *", ALLOWED));
  assert.ok(!hostAllowed("localhost:evil", ALLOWED));
  assert.ok(!hostAllowed("localhost:123456", ALLOWED));
  assert.ok(hostAllowed("[::1]:21513", ALLOWED));
});

test("originAllowed: the console's own origin only, and never an absent one", () => {
  const host = "console--ws--owner--org.cloudparse.app";
  assert.ok(originAllowed(`https://${host}`, host, ALLOWED));
  assert.ok(originAllowed("http://localhost:21513", "localhost:21513", ALLOWED));
  assert.ok(!originAllowed(undefined, host, ALLOWED));
  assert.ok(!originAllowed("null", host, ALLOWED));
  assert.ok(!originAllowed("https://evil.example.com", host, ALLOWED));
  // another allowed host that is not this console (the mini-app origin) is refused: same host:port as Host is required
  assert.ok(!originAllowed("http://localhost:21515", "localhost:21513", ALLOWED));
  assert.ok(!originAllowed("file:///x", host, ALLOWED));
});

test("tokenMatches compares without leaking the length check order", () => {
  assert.ok(tokenMatches("abc", "abc"));
  assert.ok(!tokenMatches("abd", "abc"));
  assert.ok(!tokenMatches("ab", "abc"));
  assert.ok(!tokenMatches(undefined, "abc"));
  assert.ok(!tokenMatches(null, "abc"));
});

test("rate limiter: max hits per window per key, refused hits are not counted", () => {
  let t = 0;
  const limiter = createRateLimiter(2, 1000, () => t);
  assert.ok(limiter.allow("a"));
  assert.ok(limiter.allow("a"));
  assert.ok(!limiter.allow("a"));
  assert.ok(limiter.allow("b"));
  t = 1001;
  assert.ok(limiter.allow("a"));
});
