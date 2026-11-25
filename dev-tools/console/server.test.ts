import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { startConsole } from "./server.ts";
import type { ServiceDef } from "./supervisor.ts";

async function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address() as net.AddressInfo;
      server.close(() => resolve(port));
    });
  });
}

const PART = `
console.log("part output key=S3cretPass99");
require("node:net").createServer().listen(Number(process.argv[1]), "127.0.0.1");
setInterval(() => {}, 1000);
`;

async function setup(env: Record<string, string | undefined> = {}) {
  const root = mkdtempSync(path.join(os.tmpdir(), "console-http-"));
  mkdirSync(path.join(root, "api"), { recursive: true });
  writeFileSync(path.join(root, "api", ".env"), "STORAGE_SECRET_KEY=S3cretPass99\n");
  const port = await freePort();
  const services: ServiceDef[] = [
    { id: "api", dir: "api", port, command: process.execPath, args: ["-e", PART, String(port)], env: {}, needs: [] },
  ];
  const running = await startConsole({ root, port: 0, services, env: { PATH: process.env.PATH, ...env }, probeIntervalMs: 100, stopGraceMs: 1500 });
  return { running, port };
}

function request(port: number, options: { method?: string; path?: string; headers?: Record<string, string> }): Promise<{ status: number; headers: http.IncomingHttpHeaders; body: string }> {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, method: options.method ?? "GET", path: options.path ?? "/", headers: options.headers }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers, body }));
    });
    req.on("error", reject);
    req.end();
  });
}

/** A raw WebSocket client: handshake with the given headers, then the text frames the server sends. */
function wsConnect(port: number, query: string, headers: Record<string, string>): Promise<{ status: number; messages: string[]; close(): void; wait(check: (m: string[]) => boolean): Promise<void> }> {
  return new Promise((resolve, reject) => {
    const socket = net.connect(port, "127.0.0.1");
    const key = randomBytes(16).toString("base64");
    const messages: string[] = [];
    let handshake = "";
    let status = 0;
    let rest = Buffer.alloc(0);
    socket.on("error", reject);
    socket.on("connect", () => {
      const lines = [`GET /ws${query} HTTP/1.1`, "Upgrade: websocket", "Connection: Upgrade", `Sec-WebSocket-Key: ${key}`, "Sec-WebSocket-Version: 13", ...Object.entries(headers).map(([k, v]) => `${k}: ${v}`), "", ""];
      socket.write(lines.join("\r\n"));
    });
    const waiters: (() => void)[] = [];
    const parse = () => {
      for (;;) {
        if (rest.length < 2) return;
        let length = (rest[1] as number) & 0x7f;
        let offset = 2;
        if (length === 126) {
          if (rest.length < 4) return;
          length = rest.readUInt16BE(2);
          offset = 4;
        }
        if (rest.length < offset + length) return;
        if (((rest[0] as number) & 0x0f) === 1) messages.push(rest.subarray(offset, offset + length).toString("utf8"));
        rest = rest.subarray(offset + length);
        for (const w of waiters) w();
      }
    };
    socket.on("data", (chunk) => {
      if (status === 0) {
        handshake += chunk.toString("latin1");
        const end = handshake.indexOf("\r\n\r\n");
        if (end < 0) return;
        status = Number(/^HTTP\/1.1 (\d+)/.exec(handshake)?.[1]);
        if (status === 101) {
          const accept = /Sec-WebSocket-Accept: (.+)\r\n/i.exec(handshake)?.[1];
          assert.equal(accept, createHash("sha1").update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`).digest("base64"));
          rest = Buffer.from(handshake.slice(end + 4), "latin1");
          parse();
        }
        resolve({
          status,
          messages,
          close: () => socket.destroy(),
          wait: (check) =>
            new Promise((ok, ko) => {
              const timer = setTimeout(() => ko(new Error(`timeout, got ${messages.length} messages`)), 8000);
              const test = () => {
                if (check(messages)) {
                  clearTimeout(timer);
                  ok();
                }
              };
              waiters.push(test);
              test();
            }),
        });
        return;
      }
      rest = Buffer.concat([rest, chunk as Buffer]);
      parse();
    });
  });
}

const tokenOf = (page: string) => /name="console-token" content="([0-9a-f]+)"/.exec(page)?.[1] ?? "";

test("a Host that is not allowed gets 403 on every route", async () => {
  const { running } = await setup();
  try {
    for (const p of ["/", "/healthz", "/api/state"]) {
      const res = await request(running.port, { path: p, headers: { Host: "evil.example.com" } });
      assert.equal(res.status, 403, p);
    }
    const ip = await request(running.port, { path: "/", headers: { Host: "10.1.2.3:21513" } });
    assert.equal(ip.status, 403, "an IP address in Host is refused (DNS rebinding)");
  } finally {
    await running.close();
  }
});

test("the page: security headers, nonce CSP, token, no secret", async () => {
  const { running } = await setup({ VSCODE_PROXY_URI: "https://{{port}}--main--ws--owner--org.cloudparse.app" });
  try {
    const res = await request(running.port, { headers: { Host: `localhost:${running.port}` } });
    assert.equal(res.status, 200);
    const csp = String(res.headers["content-security-policy"]);
    assert.match(csp, /script-src 'nonce-[A-Za-z0-9+/=]+'/);
    assert.match(csp, /frame-src https:\/\/miniapp--ws--owner--org\.cloudparse\.app https:\/\/plugin--ws--owner--org\.cloudparse\.app/);
    assert.match(csp, /frame-ancestors 'none'/);
    assert.equal(res.headers["x-frame-options"], "DENY");
    assert.equal(res.headers["cache-control"], "no-store");
    assert.equal(tokenOf(res.body), running.token);
    assert.ok(!res.body.includes("__TOKEN__") && !res.body.includes("__NONCE__"));
    assert.ok(!res.body.includes("S3cretPass99"));
    const state = await request(running.port, { path: "/api/state", headers: { Host: `localhost:${running.port}` } });
    const services = JSON.parse(state.body).services;
    assert.equal(services[0].links.open, "https://api--ws--owner--org.cloudparse.app/");
    assert.equal(services[0].links.page, "https://api--ws--owner--org.cloudparse.app/docs");
  } finally {
    await running.close();
  }
});

test("state-changing requests need POST, the console's Origin and the token", async () => {
  const { running } = await setup();
  const host = `localhost:${running.port}`;
  const origin = `http://${host}`;
  const act = (headers: Record<string, string>, method = "POST", p = "/api/services/api/start") => request(running.port, { method, path: p, headers: { Host: host, ...headers } });
  try {
    assert.equal((await act({}, "GET")).status, 405);
    assert.equal((await act({ "X-Console-Token": running.token })).status, 403, "no Origin");
    assert.equal((await act({ Origin: "https://evil.example.com", "X-Console-Token": running.token })).status, 403, "foreign Origin");
    assert.equal((await act({ Origin: origin })).status, 403, "no token");
    assert.equal((await act({ Origin: origin, "X-Console-Token": "0".repeat(64) })).status, 403, "wrong token");
    assert.equal((await act({ Origin: origin, "X-Console-Token": running.token }, "POST", "/api/services/rm/start")).status, 404, "unknown part");
    assert.equal((await act({ Origin: origin, "X-Console-Token": running.token }, "POST", "/api/services/api/exec")).status, 404, "unknown action");
    assert.equal((await act({ Origin: origin, "X-Console-Token": running.token }, "POST", "/api/services/..%2f..%2fetc/start")).status, 404, "no traversal");
    assert.equal(running.supervisor.status()[0]?.state, "stopped", "nothing started by the refused requests");
    const ok = await act({ Origin: origin, "X-Console-Token": running.token });
    assert.equal(ok.status, 200, ok.body);
    // a second action on the same part within 2 s is rate limited
    assert.equal((await act({ Origin: origin, "X-Console-Token": running.token }, "POST", "/api/services/api/restart")).status, 429);
  } finally {
    await running.close();
  }
});

test("no file is served: other paths are 404", async () => {
  const { running } = await setup();
  try {
    for (const p of ["/etc/passwd", "/../../etc/passwd", "/server.ts", "/api/.env", "/%2e%2e/%2e%2e/etc/passwd"]) {
      const res = await request(running.port, { path: p, headers: { Host: `localhost:${running.port}` } });
      assert.equal(res.status, 404, p);
    }
  } finally {
    await running.close();
  }
});

test("WebSocket: refused without the token, a foreign Origin or a bad Host; live state and masked logs when accepted", async () => {
  const { running } = await setup();
  const host = `localhost:${running.port}`;
  const origin = `http://${host}`;
  try {
    assert.equal((await wsConnect(running.port, "", { Host: host, Origin: origin })).status, 403, "no token");
    assert.equal((await wsConnect(running.port, `?t=${running.token}`, { Host: host })).status, 403, "no Origin");
    assert.equal((await wsConnect(running.port, `?t=${running.token}`, { Host: host, Origin: "https://evil.example.com" })).status, 403, "foreign Origin");
    assert.equal((await wsConnect(running.port, `?t=${running.token}`, { Host: "evil.example.com", Origin: "https://evil.example.com" })).status, 403, "bad Host");
    const client = await wsConnect(running.port, `?t=${running.token}`, { Host: host, Origin: origin });
    assert.equal(client.status, 101);
    await client.wait((m) => m.some((x) => JSON.parse(x).t === "state") && m.some((x) => JSON.parse(x).t === "logs"));
    const act = await request(running.port, { method: "POST", path: "/api/services/api/start", headers: { Host: host, Origin: origin, "X-Console-Token": running.token } });
    assert.equal(act.status, 200);
    await client.wait((m) => m.some((x) => x.includes("part output key=***")));
    await client.wait((m) => m.some((x) => JSON.parse(x).t === "state" && JSON.parse(x).services[0].state === "running"));
    assert.ok(!client.messages.some((x) => x.includes("S3cretPass99")), "the secret never reaches the browser");
    client.close();
  } finally {
    await running.close();
  }
});

test("a client that resets while its upgrade is refused does not crash the console", async () => {
  const { running } = await setup();
  try {
    for (let i = 0; i < 20; i++) {
      const socket = net.connect(running.port, "127.0.0.1");
      socket.on("error", () => {});
      socket.write(`GET /ws HTTP/1.1\r\nHost: localhost:${running.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: ${randomBytes(16).toString("base64")}\r\nSec-WebSocket-Version: 13\r\nOrigin: https://evil.example.com\r\n\r\n`);
      socket.resetAndDestroy();
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    const res = await request(running.port, { path: "/healthz", headers: { Host: `localhost:${running.port}` } });
    assert.equal(res.status, 200, "the console still answers");
  } finally {
    await running.close();
  }
});

test("a Host header cannot inject directives into the CSP", async () => {
  const { running } = await setup();
  try {
    const res = await request(running.port, { headers: { Host: "localhost:1 ; script-src * ; object-src *" } });
    assert.equal(res.status, 403);
  } finally {
    await running.close();
  }
});
