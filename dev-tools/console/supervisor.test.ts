import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { Supervisor, type ServiceDef, defaultServices, partEnv } from "./supervisor.ts";

async function freePort(): Promise<number> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address() as net.AddressInfo;
      server.close(() => resolve(port));
    });
  });
}

// kill -0 also succeeds on a zombie (a container whose PID 1 reaps nothing): a process counts as running unless ps says Z.
function running(pid: number): boolean {
  try {
    process.kill(pid, 0);
  } catch {
    return false;
  }
  try {
    return !execFileSync("ps", ["-o", "stat=", "-p", String(pid)], { encoding: "utf8" }).trim().startsWith("Z");
  } catch {
    return false;
  }
}

const until = async (check: () => boolean | Promise<boolean>, what: string, ms = 8000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert.fail(`timeout: ${what}`);
};

// A fake part: listens on `port`, prints a secret and a line, and starts a grandchild that holds the same process group.
const SERVER = `
const net = require("node:net");
const { spawn } = require("node:child_process");
console.log("hello from the part, secret S3cretPass99 and key " + (process.env.UP_OIDC_TOKEN ?? "no-token-in-env"));
console.log("heap option: " + (process.env.NODE_OPTIONS ?? "none"));
const child = spawn(process.execPath, ["-e", "setInterval(()=>{},1000)"], { stdio: "ignore" });
console.log("grandchild " + child.pid);
net.createServer().listen(Number(process.argv[1]), "127.0.0.1", () => console.log("listening"));
setInterval(() => {}, 1000);
`;

function fixture(port: number, extra: Partial<ServiceDef> = {}) {
  const root = mkdtempSync(path.join(os.tmpdir(), "console-"));
  mkdirSync(path.join(root, "api"), { recursive: true });
  writeFileSync(path.join(root, "api", ".env"), "DATABASE_URL=postgresql://r:S3cretPass99@h/db\nENVIRONMENT=development\n");
  const def: ServiceDef = {
    id: "api",
    dir: "api",
    port,
    command: process.execPath,
    args: ["-e", SERVER, String(port)],
    env: { NODE_OPTIONS: "--max-old-space-size=128" },
    needs: [{ path: ".env", message: "api/.env est absent" }],
    ...extra,
  };
  const supervisor = new Supervisor({ root, services: [def], env: { PATH: process.env.PATH, UP_OIDC_TOKEN: "super-secret-agent-token", HOME: root }, probeIntervalMs: 100, stopGraceMs: 1500 });
  return { root, supervisor };
}

test("the three fixed parts: ports, folders and commands", () => {
  const defs = defaultServices();
  assert.deepEqual(defs.map((d) => [d.id, d.port, d.dir]), [["api", 21514, "api"], ["miniapp", 21515, "miniapp"], ["plugin", 21516, "plugin"]]);
  assert.deepEqual(defs[0]?.args, ["run", "--env-file", ".env", "python", "-m", "app"]);
  assert.equal(defs[0]?.env.SERVER_HOST, "0.0.0.0");
  assert.deepEqual(defs[1]?.args, ["--host", "0.0.0.0"]);
  assert.deepEqual(defs[2]?.args, ["--config", "vite.dev.config.ts"]);
});

test("partEnv keeps what a dev server needs and drops the workspace's secrets", () => {
  const env = partEnv(
    { PATH: "/bin", HOME: "/h", UP_OIDC_TOKEN: "t", CODER_AGENT_TOKEN: "x", VAULT_ADDR: "v", NODE_OPTIONS: "--bad", VSCODE_PROXY_URI: "https://{{port}}--main--w--o--g.d", DEV_HUB_ORIGIN: "http://h" },
    { NODE_OPTIONS: "--max-old-space-size=384" },
  );
  assert.equal(env.PATH, "/bin");
  assert.equal(env.UP_OIDC_TOKEN, undefined);
  assert.equal(env.CODER_AGENT_TOKEN, undefined);
  assert.equal(env.VAULT_ADDR, undefined);
  assert.equal(env.NODE_OPTIONS, "--max-old-space-size=384");
  assert.equal(env.DEV_HUB_ORIGIN, "http://h");
  assert.ok(env.VSCODE_PROXY_URI);
});

test("start, running, masked logs, filtered env, then stop kills the whole process group", async () => {
  const port = await freePort();
  const { supervisor } = fixture(port);
  const lines: string[] = [];
  supervisor.on("log", (_id: string, line: string) => lines.push(line));
  try {
    assert.deepEqual(await supervisor.start("api"), { ok: true, message: "lancée" });
    await until(() => supervisor.status()[0]?.state === "running", "running");
    const logs = supervisor.logs("api").join("\n");
    assert.match(logs, /hello from the part, secret \*\*\* and key no-token-in-env/);
    assert.doesNotMatch(logs, /S3cretPass99|super-secret-agent-token/);
    assert.match(logs, /heap option: --max-old-space-size=128/);
    assert.ok(lines.some((l) => l.includes("listening")), "live log event");
    const grandchild = Number(/grandchild (\d+)/.exec(logs)?.[1]);
    assert.ok(grandchild > 0);
    const pid = supervisor.status()[0]?.pid as number;
    assert.ok(running(grandchild), "the grandchild runs");
    assert.deepEqual(await supervisor.stop("api"), { ok: true, message: "arrêtée" });
    assert.equal(supervisor.status()[0]?.state, "stopped");
    assert.ok(!running(grandchild), "the grandchild of the group is gone");
    assert.ok(!running(pid), "the leader is gone");
    assert.equal(await supervisor.start("api").then((r) => r.ok), true, "can start again after a stop");
    await until(() => supervisor.status()[0]?.state === "running", "running again");
  } finally {
    await supervisor.close();
  }
});

test("restart gives a new process and the port answers again", async () => {
  const port = await freePort();
  const { supervisor } = fixture(port);
  try {
    await supervisor.start("api");
    await until(() => supervisor.status()[0]?.state === "running", "running");
    const first = supervisor.status()[0]?.pid;
    const result = await supervisor.restart("api");
    assert.equal(result.ok, true);
    await until(() => supervisor.status()[0]?.state === "running", "running after restart");
    assert.notEqual(supervisor.status()[0]?.pid, first);
  } finally {
    await supervisor.close();
  }
});

test("a part that exits with an error is crashed, with its exit code", async () => {
  const port = await freePort();
  const { supervisor } = fixture(port, { args: ["-e", "console.log('boom'); process.exit(3)"] });
  try {
    await supervisor.start("api");
    await until(() => supervisor.status()[0]?.state === "crashed", "crashed");
    assert.equal(supervisor.status()[0]?.exitCode, 3);
    assert.match(supervisor.status()[0]?.message ?? "", /code 3/);
    assert.match(supervisor.logs("api").join("\n"), /boom/);
  } finally {
    await supervisor.close();
  }
});

test("a missing dependency or settings file blocks the start with the reason", async () => {
  const port = await freePort();
  const { root, supervisor } = fixture(port, { needs: [{ path: "node_modules/.bin/vite", message: "dépendances absentes" }] });
  try {
    const result = await supervisor.start("api");
    assert.equal(result.ok, false);
    assert.equal(result.message, "dépendances absentes");
    assert.equal(supervisor.status()[0]?.state, "blocked");
    assert.ok(root);
  } finally {
    await supervisor.close();
  }
});

test("a port that already answers is external: the console neither starts nor stops it", async () => {
  const port = await freePort();
  const { supervisor } = fixture(port);
  const outside = net.createServer();
  await new Promise<void>((resolve) => outside.listen(port, "127.0.0.1", () => resolve()));
  try {
    await until(() => supervisor.status()[0]?.state === "external", "external");
    const started = await supervisor.start("api");
    assert.equal(started.ok, false);
    const stopped = await supervisor.stop("api");
    assert.equal(stopped.ok, false);
    assert.match(stopped.message, /terminal/);
  } finally {
    outside.close();
    await supervisor.close();
  }
});

test("an unknown part is refused", async () => {
  const { supervisor } = fixture(await freePort());
  try {
    assert.equal((await supervisor.start("rm -rf")).ok, false);
    assert.equal(supervisor.has("../etc"), false);
  } finally {
    await supervisor.close();
  }
});
