// Run by `npm test` in miniapp/ (node's own test runner, no dependency).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  appButtonHosts,
  devAllowedHosts,
  hostGuard,
  hostNameOf,
  isAllowedHost,
} from "./hostGuard.ts";

const ALLOWED = [
  "21515--main--ws--me--org.apps.example.com",
  ".dev.example.com",
];

test("loopback names are always allowed, with or without a port", () => {
  for (const host of [
    "localhost",
    "localhost:21515",
    "127.0.0.1:21515",
    "[::1]:21515",
  ]) {
    assert.equal(isAllowedHost(host, []), true, host);
  }
});

test("any other IP address is refused, IPv4 and IPv6", () => {
  for (const host of [
    "10.0.0.5:21515",
    "192.168.1.16",
    "[fe80::1]:21515",
    "0.0.0.0:21515",
  ]) {
    assert.equal(isAllowedHost(host, ALLOWED), false, host);
  }
});

test("a missing or empty Host is refused", () => {
  assert.equal(isAllowedHost(undefined, ALLOWED), false);
  assert.equal(isAllowedHost("", ALLOWED), false);
});

test("the listed names and their dotted subdomains are allowed, others are not", () => {
  assert.equal(
    isAllowedHost("21515--main--ws--me--org.apps.example.com", ALLOWED),
    true,
  );
  assert.equal(isAllowedHost("A.dev.example.com:21515", ALLOWED), true);
  assert.equal(isAllowedHost("dev.example.com", ALLOWED), true);
  assert.equal(isAllowedHost("evil.example.com", ALLOWED), false);
  assert.equal(isAllowedHost("xdev.example.com", ALLOWED), false);
});

test("hostNameOf strips the port", () => {
  assert.equal(hostNameOf("Example.COM:80"), "example.com");
  assert.equal(hostNameOf("[::1]:21515"), "[::1]");
});

test("devAllowedHosts reads DEV_ALLOWED_HOSTS and the Coder port URL", () => {
  const hosts = devAllowedHosts(21515, {
    DEV_ALLOWED_HOSTS: " a.example.com, ,.b.example.com",
    VSCODE_PROXY_URI: "https://{{port}}--main--ws--me--org.apps.example.com",
  });
  assert.deepEqual(hosts, [
    "a.example.com",
    ".b.example.com",
    "21515--main--ws--me--org.apps.example.com",
  ]);
});

test("devAllowedHosts ignores an unusable VSCODE_PROXY_URI", () => {
  assert.deepEqual(
    devAllowedHosts(21515, { VSCODE_PROXY_URI: "not a url {{port}}" }),
    [],
  );
});

test("the middleware answers 403 and does not call next for a forged Host", () => {
  let handler: (req: unknown, res: unknown, next: () => void) => void =
    () => {};
  hostGuard(ALLOWED).configureServer({
    middlewares: {
      use: (fn) => {
        handler = fn as typeof handler;
      },
    },
  });
  const res = {
    body: "",
    end(b: string) {
      this.body = b;
    },
    setHeader() {},
    statusCode: 200,
  };
  let nexted = false;

  handler({ headers: { host: "10.0.0.5:21515" } }, res, () => {
    nexted = true;
  });
  assert.equal(res.statusCode, 403);
  assert.equal(nexted, false);

  handler({ headers: { host: "localhost:21515" } }, res, () => {
    nexted = true;
  });
  assert.equal(nexted, true);
});

test("appButtonHosts derives the Coder app button host from the port URL", () => {
  const env = {
    VSCODE_PROXY_URI:
      "https://{{port}}--main--test2--thoughtful-lawson93--app.cloudparse.app/",
  };
  assert.deepEqual(appButtonHosts(21516, "plugin", env), [
    "plugin--test2--thoughtful-lawson93--app.cloudparse.app",
  ]);
  assert.deepEqual(appButtonHosts(21516, "plugin", {}), []);
  assert.deepEqual(appButtonHosts(21516, "plugin", { VSCODE_PROXY_URI: "nope" }), []);
  assert.ok(
    isAllowedHost("plugin--test2--thoughtful-lawson93--app.cloudparse.app", [
      ...appButtonHosts(21516, "plugin", env),
    ]),
  );
});
